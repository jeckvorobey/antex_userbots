"""Тесты container handover и graceful lifecycle swarm-процесса."""

import asyncio
import os
import signal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import aiosqlite
import pytest


@pytest.mark.asyncio
async def test_runtime_lock_waits_until_first_owner_releases(tmp_path):
    """Проверяет передачу runtime-владения между двумя containers."""
    from core.runtime_lock import RuntimeInstanceLock

    db_path = tmp_path / "history.db"
    first = RuntimeInstanceLock(str(db_path), poll_interval_seconds=0.01, timeout_seconds=1.0)
    second = RuntimeInstanceLock(str(db_path), poll_interval_seconds=0.01, timeout_seconds=1.0)

    assert await first.acquire() is True
    second_acquire = asyncio.create_task(second.acquire())
    await asyncio.sleep(0.03)
    assert second_acquire.done() is False

    first.release()
    assert await second_acquire is True
    second.release()


@pytest.mark.asyncio
async def test_runtime_lock_times_out_when_owner_does_not_release(tmp_path):
    """Проверяет ограниченный timeout ожидания зависшего владельца."""
    from core.runtime_lock import RuntimeInstanceLock, RuntimeLockTimeoutError

    db_path = tmp_path / "history.db"
    first = RuntimeInstanceLock(str(db_path), poll_interval_seconds=0.005, timeout_seconds=1.0)
    second = RuntimeInstanceLock(str(db_path), poll_interval_seconds=0.005, timeout_seconds=0.02)
    await first.acquire()

    try:
        with pytest.raises(RuntimeLockTimeoutError, match="runtime lock"):
            await second.acquire()
    finally:
        second.release()
        first.release()


@pytest.mark.asyncio
async def test_runtime_lock_stops_waiting_on_shutdown_signal(tmp_path):
    """Проверяет прерывание ожидания lock при остановке нового container."""
    from core.runtime_lock import RuntimeInstanceLock

    db_path = tmp_path / "history.db"
    first = RuntimeInstanceLock(str(db_path), poll_interval_seconds=0.01, timeout_seconds=1.0)
    second = RuntimeInstanceLock(str(db_path), poll_interval_seconds=0.01, timeout_seconds=1.0)
    shutdown_event = asyncio.Event()
    await first.acquire()
    waiting = asyncio.create_task(second.acquire(shutdown_event=shutdown_event))
    await asyncio.sleep(0.02)

    shutdown_event.set()

    assert await waiting is False
    second.release()
    first.release()


@pytest.mark.asyncio
async def test_runtime_lock_is_noop_for_memory_database(tmp_path):
    """Проверяет, что unit tests с :memory: не создают lock-файл."""
    from core.runtime_lock import RuntimeInstanceLock

    runtime_lock = RuntimeInstanceLock(":memory:")

    assert await runtime_lock.acquire() is True
    assert runtime_lock.lock_path is None
    runtime_lock.release()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="Проверка предназначена для Linux runtime")
async def test_runtime_lock_does_not_follow_symbolic_link(tmp_path):
    """Проверяет, что подменённый lock-файл не позволяет перезаписать другой файл."""
    from core.runtime_lock import RuntimeInstanceLock

    protected_file = tmp_path / "protected.txt"
    protected_file.write_text("do-not-truncate", encoding="utf-8")
    db_path = tmp_path / "history.db"
    lock_path = tmp_path / "history.db.runtime.lock"
    lock_path.symlink_to(protected_file)
    runtime_lock = RuntimeInstanceLock(str(db_path))

    with pytest.raises(OSError):
        await runtime_lock.acquire()

    assert protected_file.read_text(encoding="utf-8") == "do-not-truncate"
    runtime_lock.release()


def test_runtime_volume_guard_accepts_matching_marker_on_linux_mount(tmp_path):
    """Проверяет successful validation корректного Coolify volume."""
    from core.runtime_volume import RuntimeVolumeGuard

    mount_path = tmp_path / "data"
    mount_path.mkdir()
    marker_path = mount_path / ".coolify-resource-uuid"
    marker_path.write_text("resource-123\n", encoding="utf-8")
    mountinfo_path = tmp_path / "mountinfo"
    mountinfo_path.write_text(
        f"36 25 0:32 / {mount_path} rw,relatime - ext4 /dev/root rw\n",
        encoding="utf-8",
    )

    guard = RuntimeVolumeGuard(
        str(mount_path / "history.db"),
        coolify_resource_uuid="resource-123",
        expected_mount_path=mount_path,
        mountinfo_path=mountinfo_path,
    )

    assert guard.verify() is True


def test_runtime_volume_guard_rejects_directory_missing_from_mountinfo(tmp_path):
    """Проверяет fail-closed startup для image directory вместо volume mount."""
    from core.runtime_volume import RuntimeVolumeGuard, RuntimeVolumeValidationError

    mount_path = tmp_path / "data"
    mount_path.mkdir()
    (mount_path / ".coolify-resource-uuid").write_text("resource-123\n", encoding="utf-8")
    mountinfo_path = tmp_path / "mountinfo"
    mountinfo_path.write_text("", encoding="utf-8")
    guard = RuntimeVolumeGuard(
        str(mount_path / "history.db"),
        coolify_resource_uuid="resource-123",
        expected_mount_path=mount_path,
        mountinfo_path=mountinfo_path,
    )

    with pytest.raises(RuntimeVolumeValidationError, match="mount"):
        guard.verify()


@pytest.mark.parametrize("marker_value", [None, "", "another-resource"])
def test_runtime_volume_guard_rejects_missing_empty_or_mismatched_marker(tmp_path, marker_value):
    """Проверяет, что wrong volume нельзя автоматически принять за production state."""
    from core.runtime_volume import RuntimeVolumeGuard, RuntimeVolumeValidationError

    mount_path = tmp_path / "data"
    mount_path.mkdir()
    if marker_value is not None:
        (mount_path / ".coolify-resource-uuid").write_text(marker_value, encoding="utf-8")
    mountinfo_path = tmp_path / "mountinfo"
    mountinfo_path.write_text(
        f"36 25 0:32 / {mount_path} rw,relatime - ext4 /dev/root rw\n",
        encoding="utf-8",
    )
    guard = RuntimeVolumeGuard(
        str(mount_path / "history.db"),
        coolify_resource_uuid="resource-123",
        expected_mount_path=mount_path,
        mountinfo_path=mountinfo_path,
    )

    with pytest.raises(RuntimeVolumeValidationError, match="marker"):
        guard.verify()


def test_runtime_volume_guard_rejects_symbolic_link_marker(tmp_path):
    """Проверяет, что identity marker нельзя подменить symbolic link."""
    from core.runtime_volume import RuntimeVolumeGuard, RuntimeVolumeValidationError

    mount_path = tmp_path / "data"
    mount_path.mkdir()
    marker_target = tmp_path / "marker-target"
    marker_target.write_text("resource-123", encoding="utf-8")
    (mount_path / ".coolify-resource-uuid").symlink_to(marker_target)
    mountinfo_path = tmp_path / "mountinfo"
    mountinfo_path.write_text(
        f"36 25 0:32 / {mount_path} rw,relatime - ext4 /dev/root rw\n",
        encoding="utf-8",
    )
    guard = RuntimeVolumeGuard(
        str(mount_path / "history.db"),
        coolify_resource_uuid="resource-123",
        expected_mount_path=mount_path,
        mountinfo_path=mountinfo_path,
    )

    with pytest.raises(RuntimeVolumeValidationError, match="marker"):
        guard.verify()


def test_runtime_volume_guard_skips_local_and_memory_databases(tmp_path):
    """Проверяет сохранение local development и in-memory tests."""
    from core.runtime_volume import RuntimeVolumeGuard

    expected_mount_path = tmp_path / "production-data"
    mountinfo_path = tmp_path / "missing-mountinfo"

    assert RuntimeVolumeGuard(
        str(tmp_path / "local" / "history.db"),
        expected_mount_path=expected_mount_path,
        mountinfo_path=mountinfo_path,
    ).verify() is False
    assert RuntimeVolumeGuard(
        ":memory:",
        expected_mount_path=expected_mount_path,
        mountinfo_path=mountinfo_path,
    ).verify() is False


@pytest.mark.asyncio
async def test_application_validates_volume_before_lock_and_bootstrap(monkeypatch):
    """Проверяет fail-closed volume guard до любых runtime resources."""
    import run

    events: list[str] = []

    class FailingGuard:
        def verify(self):
            events.append("volume-validation")
            raise RuntimeError("invalid volume")

    lock_factory = Mock(side_effect=lambda *_args, **_kwargs: events.append("lock-created"))
    bootstrap = AsyncMock(side_effect=lambda *_args: events.append("sqlite-bootstrap"))
    monkeypatch.setattr(run, "RuntimeVolumeGuard", lambda *_args, **_kwargs: FailingGuard())
    monkeypatch.setattr(run, "RuntimeInstanceLock", lock_factory)
    monkeypatch.setattr(run, "_build_runtime_context", bootstrap)

    with pytest.raises(RuntimeError, match="invalid volume"):
        await run._run_application(SimpleNamespace(db_path="/app/data/history.db"), asyncio.Event())

    assert events == ["volume-validation"]
    lock_factory.assert_not_called()
    bootstrap.assert_not_awaited()


def test_install_signal_handlers_registers_sigterm_and_sigint():
    """Проверяет регистрацию Docker SIGTERM и интерактивного SIGINT."""
    import run

    loop = SimpleNamespace(add_signal_handler=Mock(), remove_signal_handler=Mock())
    shutdown_event = asyncio.Event()

    installed = run._install_signal_handlers(loop, shutdown_event)

    assert installed == [signal.SIGTERM, signal.SIGINT]
    assert [call.args[0] for call in loop.add_signal_handler.call_args_list] == [signal.SIGTERM, signal.SIGINT]


@pytest.mark.asyncio
async def test_application_shutdown_order_stops_scheduler_before_releasing_lock(monkeypatch):
    """Проверяет порядок cleanup при сигнале во время supervise-loop."""
    import run

    events: list[str] = []
    shutdown_event = asyncio.Event()
    swarm_started = asyncio.Event()
    runtime = SimpleNamespace(close=AsyncMock(side_effect=lambda: events.append("sqlite-closed")))

    class FakeLock:
        lock_path = "/tmp/history.db.runtime.lock"

        async def acquire(self, *, shutdown_event=None):
            events.append("lock-acquired")
            return True

        def release(self):
            events.append("lock-released")

    scheduler = SimpleNamespace(
        start=Mock(side_effect=lambda: events.append("scheduler-started")),
        shutdown=Mock(side_effect=lambda wait=False: events.append("scheduler-stopped")),
    )

    async def run_swarm(*_args):
        events.append("swarm-started")
        swarm_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            events.append("telegram-stopped")

    monkeypatch.setattr(run, "CONTAINER_HANDOVER_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(run, "RuntimeInstanceLock", lambda *_args, **_kwargs: FakeLock())
    monkeypatch.setattr(run, "_build_runtime_context", AsyncMock(return_value=runtime))
    monkeypatch.setattr(run, "AsyncIOScheduler", lambda: scheduler)
    monkeypatch.setattr(run, "_run_swarm_mode", run_swarm)

    application = asyncio.create_task(run._run_application(SimpleNamespace(db_path="data/history.db"), shutdown_event))
    await swarm_started.wait()
    shutdown_event.set()
    await application

    assert events.index("scheduler-stopped") < events.index("telegram-stopped")
    assert events.index("telegram-stopped") < events.index("sqlite-closed")
    assert events.index("sqlite-closed") < events.index("lock-released")


@pytest.mark.asyncio
async def test_runtime_context_retries_only_sqlite_lock_errors(monkeypatch):
    """Проверяет ограниченный retry bootstrap при временном SQLite lock."""
    import run

    expected_runtime = SimpleNamespace()
    build_once = AsyncMock(
        side_effect=[
            aiosqlite.OperationalError("database is locked"),
            expected_runtime,
        ]
    )
    sleep = AsyncMock()
    monkeypatch.setattr(run, "_build_runtime_context_once", build_once)
    monkeypatch.setattr(run.asyncio, "sleep", sleep)
    monkeypatch.setattr(run, "SQLITE_BOOTSTRAP_RETRY_DELAYS_SECONDS", (0.25,))

    result = await run._build_runtime_context(SimpleNamespace())

    assert result is expected_runtime
    assert build_once.await_count == 2
    sleep.assert_awaited_once_with(0.25)


@pytest.mark.asyncio
async def test_runtime_context_does_not_retry_unrelated_sqlite_error(monkeypatch):
    """Проверяет, что unrelated OperationalError не маскируется retry-логикой."""
    import run

    build_once = AsyncMock(side_effect=aiosqlite.OperationalError("no such table: messages"))
    sleep = AsyncMock()
    monkeypatch.setattr(run, "_build_runtime_context_once", build_once)
    monkeypatch.setattr(run.asyncio, "sleep", sleep)

    with pytest.raises(aiosqlite.OperationalError, match="no such table"):
        await run._build_runtime_context(SimpleNamespace())

    build_once.assert_awaited_once()
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_context_once_closes_partial_history_connection(monkeypatch):
    """Проверяет закрытие частичного connection перед повтором bootstrap."""
    import run

    history = SimpleNamespace(
        init_db=AsyncMock(side_effect=aiosqlite.OperationalError("database is locked")),
        close=AsyncMock(),
    )
    monkeypatch.setattr(run, "MessageHistory", lambda _db_path: history)

    with pytest.raises(aiosqlite.OperationalError, match="database is locked"):
        await run._build_runtime_context_once(SimpleNamespace(db_path="history.db"))

    history.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_runtime_context_once_preserves_bootstrap_error_when_cleanup_fails(monkeypatch):
    """Проверяет best-effort cleanup без маскировки исходной SQLite-ошибки."""
    import run

    history = SimpleNamespace(
        init_db=AsyncMock(),
        prune_older_than=AsyncMock(),
        close=AsyncMock(side_effect=RuntimeError("history close failed")),
    )
    exchange_store = SimpleNamespace(
        init_db=AsyncMock(side_effect=aiosqlite.OperationalError("database is locked")),
        prune_older_than=AsyncMock(),
        close=AsyncMock(),
    )
    topic_selector = SimpleNamespace(load=AsyncMock(), topics=[])
    monkeypatch.setattr(run, "MessageHistory", lambda _db_path: history)
    monkeypatch.setattr(run, "ExchangeStore", lambda _db_path: exchange_store)
    monkeypatch.setattr(run, "PromptLoader", Mock(return_value=SimpleNamespace()))
    monkeypatch.setattr(run, "GeminiClient", Mock(return_value=SimpleNamespace()))
    monkeypatch.setattr(run, "TopicSelector", Mock(return_value=topic_selector))
    monkeypatch.setattr(run, "PromptComposer", Mock(return_value=SimpleNamespace()))
    settings = SimpleNamespace(
        db_path="history.db",
        prompts_dir="prompts",
        topics_path="topics.md",
        bot_profiles_dir="bots",
        gemini_api_key="test-key",
        gemini_model="test-model",
        proxy_url=None,
        gemini_fallback_model=None,
        gemini_max_retries=0,
        gemini_retry_backoff_seconds=0.0,
        gemini_retry_jitter_seconds=0.0,
        gemini_request_timeout_seconds=1.0,
        gemini_temperature=0.5,
        swarm_history_retention_days=30,
    )

    with pytest.raises(aiosqlite.OperationalError, match="database is locked"):
        await run._build_runtime_context_once(settings)

    history.close.assert_awaited_once()
    exchange_store.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_runtime_context_close_continues_after_one_resource_error(caplog):
    """Проверяет best-effort закрытие обеих SQLite-сессий."""
    import run

    history = SimpleNamespace(close=AsyncMock(side_effect=RuntimeError("history close failed")))
    exchange_store = SimpleNamespace(close=AsyncMock())
    runtime = run.RuntimeContext(
        history=history,
        prompt_loader=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        exchange_store=exchange_store,
    )

    await runtime.close()

    history.close.assert_awaited_once()
    exchange_store.close.assert_awaited_once()
    assert "history close failed" in caplog.text


@pytest.mark.asyncio
async def test_runtime_context_close_times_out_hanging_resource_and_closes_other(monkeypatch, caplog):
    """Проверяет bounded SQLite cleanup и продолжение после timeout."""
    import run

    async def hang_forever():
        await asyncio.Event().wait()

    history = SimpleNamespace(close=AsyncMock(side_effect=hang_forever))
    exchange_store = SimpleNamespace(close=AsyncMock())
    runtime = run.RuntimeContext(
        history=history,
        prompt_loader=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        exchange_store=exchange_store,
    )
    monkeypatch.setattr(run, "RUNTIME_RESOURCE_CLOSE_TIMEOUT_SECONDS", 0.01)

    await asyncio.wait_for(runtime.close(), timeout=0.2)

    history.close.assert_awaited_once()
    exchange_store.close.assert_awaited_once()
    assert "timeout" in caplog.text.lower()


@pytest.mark.asyncio
async def test_application_releases_lock_after_runtime_close_timeout(monkeypatch, caplog):
    """Проверяет release runtime lock после bounded попыток закрытия SQLite."""
    import run

    events: list[str] = []
    swarm_started = asyncio.Event()
    shutdown_event = asyncio.Event()

    async def hang_forever():
        await asyncio.Event().wait()

    runtime = run.RuntimeContext(
        history=SimpleNamespace(close=AsyncMock(side_effect=hang_forever)),
        prompt_loader=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        exchange_store=SimpleNamespace(close=AsyncMock(side_effect=lambda: events.append("exchange-closed"))),
    )

    class FakeGuard:
        def verify(self):
            events.append("volume-validated")
            return True

    class FakeLock:
        lock_path = "/app/data/history.db.runtime.lock"

        async def acquire(self, *, shutdown_event=None):
            events.append("lock-acquired")
            return True

        def release(self):
            events.append("lock-released")

    scheduler = SimpleNamespace(start=Mock(), shutdown=Mock())

    async def run_swarm(*_args):
        swarm_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(run, "CONTAINER_HANDOVER_DELAY_SECONDS", 0.0)
    monkeypatch.setattr(run, "RUNTIME_RESOURCE_CLOSE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(run, "RuntimeVolumeGuard", lambda *_args, **_kwargs: FakeGuard())
    monkeypatch.setattr(run, "RuntimeInstanceLock", lambda *_args, **_kwargs: FakeLock())
    monkeypatch.setattr(run, "_build_runtime_context", AsyncMock(return_value=runtime))
    monkeypatch.setattr(run, "AsyncIOScheduler", lambda: scheduler)
    monkeypatch.setattr(run, "_run_swarm_mode", run_swarm)

    application = asyncio.create_task(
        run._run_application(SimpleNamespace(db_path="/app/data/history.db"), shutdown_event)
    )
    await swarm_started.wait()
    shutdown_event.set()
    await asyncio.wait_for(application, timeout=0.2)

    assert events.index("exchange-closed") < events.index("lock-released")
    assert "timeout" in caplog.text.lower()
