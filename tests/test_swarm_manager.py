"""Тесты менеджера swarm-клиентов."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from core.runtime_models import SwarmBotProfile
from userbot.swarm_manager import SwarmManager


@pytest.mark.asyncio
async def test_swarm_manager_starts_enabled_bots_and_collects_user_ids():
    """Проверяет запуск enabled-ботов и сбор их Telegram user_id."""
    anna_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )
    john_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=202)),
        run_until_disconnected=AsyncMock(),
    )

    manager = SwarmManager(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", enabled=True),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", enabled=False),
            SwarmBotProfile(id="john", session_string="john", persona_file="john.md", enabled=True),
        ],
        client_factory=lambda profile: anna_client if profile.id == "anna" else john_client,
    )

    await manager.start()

    anna_client.start.assert_awaited_once()
    john_client.start.assert_awaited_once()
    assert manager.swarm_user_ids == {101, 202}
    assert sorted(manager.active_bot_ids) == ["anna", "john"]


@pytest.mark.asyncio
async def test_swarm_manager_prioritizes_human_slot_over_scheduled():
    """Проверяет, что scheduled задача уступает human reply."""
    fake_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )
    manager = SwarmManager(
        bot_profiles=[SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md")],
        client_factory=lambda _profile: fake_client,
    )
    await manager.start()

    human_entered = asyncio.Event()
    scheduled_result: list[bool] = []

    async def human_task():
        async with manager.human_slot("anna"):
            human_entered.set()
            await asyncio.sleep(0)

    async def scheduled_task():
        await human_entered.wait()
        async with manager.scheduled_slot("anna") as acquired:
            scheduled_result.append(acquired)

    await asyncio.gather(human_task(), scheduled_task())

    assert scheduled_result == [False]


@pytest.mark.asyncio
async def test_swarm_manager_reconnects_after_client_error():
    """Проверяет reconnect loop после ошибки клиента."""
    stop_signal = asyncio.Event()

    async def failing_run():
        if not stop_signal.is_set():
            stop_signal.set()
            raise RuntimeError("boom")
        return None

    fake_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(side_effect=failing_run),
    )
    profile = SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md")
    manager = SwarmManager(
        bot_profiles=[profile],
        client_factory=lambda _profile: fake_client,
        reconnect_backoff_seconds=(0.0,),
    )
    await manager.start()

    supervise_task = asyncio.create_task(manager.supervise_bot("anna"))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await manager.stop()
    supervise_task.cancel()
    await asyncio.gather(supervise_task, return_exceptions=True)

    assert fake_client.start.await_count >= 2
    assert manager.runtime_states["anna"].reconnect_attempts >= 1


@pytest.mark.asyncio
async def test_swarm_manager_skips_bot_when_startup_fails():
    """Проверяет, что бот с ошибкой startup не попадает в активный пул."""
    anna_client = SimpleNamespace(
        start=AsyncMock(side_effect=RuntimeError("join failed")),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )
    john_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=202)),
        run_until_disconnected=AsyncMock(),
    )

    manager = SwarmManager(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", enabled=True),
            SwarmBotProfile(id="john", session_string="john", persona_file="john.md", enabled=True),
        ],
        client_factory=lambda profile: anna_client if profile.id == "anna" else john_client,
    )

    await manager.start()

    assert manager.active_bot_ids == ["john"]
    assert set(manager.clients) == {"john"}
    assert manager.swarm_user_ids == {202}
    assert manager.runtime_states["anna"].status == "error"


@pytest.mark.asyncio
async def test_swarm_manager_disconnects_client_cancelled_during_startup_hook():
    """Проверяет cleanup клиента при SIGTERM во время долгого startup hook."""
    hook_started = asyncio.Event()
    fake_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )

    async def startup_hook(_profile, _client):
        hook_started.set()
        await asyncio.Event().wait()

    manager = SwarmManager(
        bot_profiles=[SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md")],
        client_factory=lambda _profile: fake_client,
        startup_hook=startup_hook,
    )
    startup = asyncio.create_task(manager.start())
    await hook_started.wait()

    startup.cancel()
    await asyncio.gather(startup, return_exceptions=True)

    fake_client.stop.assert_awaited_once()
    assert manager.active_bot_ids == []
    assert manager.clients == {}


@pytest.mark.asyncio
async def test_swarm_manager_stops_remaining_clients_after_one_stop_error(caplog):
    """Проверяет best-effort cleanup всех clients при единичной ошибке disconnect."""
    broken_client = SimpleNamespace(stop=AsyncMock(side_effect=RuntimeError("disconnect failed")))
    healthy_client = SimpleNamespace(stop=AsyncMock())
    manager = SwarmManager(bot_profiles=[], client_factory=Mock())
    manager.clients = {"broken": broken_client, "healthy": healthy_client}

    await manager.stop()

    broken_client.stop.assert_awaited_once()
    healthy_client.stop.assert_awaited_once()
    assert "disconnect failed" in caplog.text


@pytest.mark.asyncio
async def test_swarm_manager_times_out_hanging_client_and_stops_remaining_clients(caplog):
    """Проверяет bounded disconnect всех registered clients."""

    async def hang_forever():
        await asyncio.Event().wait()

    hanging_client = SimpleNamespace(stop=AsyncMock(side_effect=hang_forever))
    healthy_client = SimpleNamespace(stop=AsyncMock())
    manager = SwarmManager(
        bot_profiles=[],
        client_factory=Mock(),
        client_stop_timeout_seconds=0.01,
    )
    manager.clients = {"hanging": hanging_client, "healthy": healthy_client}

    await asyncio.wait_for(manager.stop(), timeout=0.2)

    hanging_client.stop.assert_awaited_once()
    healthy_client.stop.assert_awaited_once()
    assert "timeout" in caplog.text.lower()


@pytest.mark.asyncio
async def test_swarm_manager_times_out_unregistered_client_cancelled_during_startup(caplog):
    """Проверяет deadline cleanup незарегистрированного startup client."""
    hook_started = asyncio.Event()

    async def startup_hook(_profile, _client):
        hook_started.set()
        await asyncio.Event().wait()

    async def hang_forever():
        await asyncio.Event().wait()

    fake_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(side_effect=hang_forever),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )
    manager = SwarmManager(
        bot_profiles=[SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md")],
        client_factory=lambda _profile: fake_client,
        startup_hook=startup_hook,
        client_stop_timeout_seconds=0.01,
    )
    startup = asyncio.create_task(manager.start())
    await hook_started.wait()

    startup.cancel()
    await asyncio.wait_for(asyncio.gather(startup, return_exceptions=True), timeout=0.2)

    fake_client.stop.assert_awaited_once()
    assert manager.clients == {}
    assert "timeout" in caplog.text.lower()
