"""Тесты общего SQLite-соединения и конкурентных операций."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock

import aiosqlite
import pytest

from ai.history import MessageHistory
from storage.sqlite_database import SQLiteDatabase
from userbot.exchange_store import ExchangeStore


async def _build_persistence(db_path: str) -> tuple[SQLiteDatabase, MessageHistory, ExchangeStore]:
    database = SQLiteDatabase(db_path)
    await database.open()
    history = MessageHistory(database)
    exchange_store = ExchangeStore(database)
    await history.init_db()
    await exchange_store.init_db()
    return database, history, exchange_store


async def test_sqlite_database_configures_connection(tmp_path):
    """Проверяет обязательные PRAGMA общего файлового соединения."""
    database = SQLiteDatabase(str(tmp_path / "history.db"))
    await database.open()
    try:
        values = {}
        for pragma in ("journal_mode", "synchronous", "busy_timeout", "foreign_keys"):
            async with database.connection.execute(f"PRAGMA {pragma}") as cursor:
                values[pragma] = (await cursor.fetchone())[0]
    finally:
        await database.close()

    assert values == {
        "journal_mode": "wal",
        "synchronous": 1,
        "busy_timeout": 30000,
        "foreign_keys": 1,
    }


async def test_sqlite_database_restricts_file_permissions(tmp_path):
    """Проверяет, что persisted history доступна только владельцу процесса."""
    db_path = tmp_path / "history.db"
    db_path.touch(mode=0o666)
    database = SQLiteDatabase(str(db_path))

    await database.open()
    try:
        assert db_path.stat().st_mode & 0o777 == 0o600
    finally:
        await database.close()


async def test_sqlite_database_restricts_wal_sidecar_permissions_after_write(tmp_path):
    """Проверяет owner-only права SQLite WAL и SHM после записи."""
    db_path = tmp_path / "history.db"
    database = SQLiteDatabase(str(db_path))

    await database.open()
    try:
        await database.execute("create_messages", "CREATE TABLE messages (id INTEGER PRIMARY KEY)")
        sidecar_paths = (db_path.with_name("history.db-wal"), db_path.with_name("history.db-shm"))
        for sidecar_path in sidecar_paths:
            assert sidecar_path.exists()
            sidecar_path.chmod(0o666)
        await database.execute("insert_message", "INSERT INTO messages DEFAULT VALUES")
        for sidecar_path in sidecar_paths:
            assert sidecar_path.stat().st_mode & 0o777 == 0o600
    finally:
        await database.close()


async def test_sqlite_database_retries_temporary_lock(monkeypatch, caplog):
    """Проверяет retry временной блокировки с именем операции."""
    database = SQLiteDatabase(":memory:")
    await database.open()
    monkeypatch.setattr(database, "RETRY_DELAYS", (0, 0, 0, 0))
    calls = 0

    async def temporarily_locked(_connection):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise aiosqlite.OperationalError("database is locked")
        return "ok"

    with caplog.at_level(logging.WARNING):
        result = await database.write("save_message", temporarily_locked)
    await database.close()

    assert result == "ok"
    assert calls == 2
    assert "attempt=2/5 delay=0s operation=save_message" in caplog.text


async def test_sqlite_database_raises_after_five_attempts(monkeypatch):
    """Проверяет пять попыток и четыре задержки перед окончательной ошибкой."""
    database = SQLiteDatabase(":memory:")
    await database.open()
    monkeypatch.setattr(database, "RETRY_DELAYS", (0, 0, 0, 0))
    rollback = AsyncMock(wraps=database.connection.rollback)
    monkeypatch.setattr(database.connection, "rollback", rollback)
    calls = 0

    async def always_locked(_connection):
        nonlocal calls
        calls += 1
        raise aiosqlite.OperationalError("database is locked")

    try:
        with pytest.raises(aiosqlite.OperationalError, match="database is locked"):
            await database.write("always_locked", always_locked)
    finally:
        await database.close()

    assert calls == 5
    assert rollback.await_count == 5


async def test_schema_initialization_succeeds_after_temporary_lock(monkeypatch):
    """Проверяет retry всей инициализации схемы после краткой блокировки."""
    database = SQLiteDatabase(":memory:")
    await database.open()
    history = MessageHistory(database)
    original_write = database.write
    calls = 0

    async def initialize_with_lock(operation, callback):
        nonlocal calls
        if operation == "init_message_history" and calls == 0:
            calls += 1

            async def locked_once(connection):
                nonlocal calls
                if calls == 1:
                    calls += 1
                    raise aiosqlite.OperationalError("database table is locked")
                return await callback(connection)

            monkeypatch.setattr(database, "RETRY_DELAYS", (0, 0, 0, 0))
            return await original_write(operation, locked_once)
        return await original_write(operation, callback)

    monkeypatch.setattr(database, "write", initialize_with_lock)
    try:
        await history.init_db()
        async with database.connection.execute("SELECT name FROM sqlite_master WHERE name = 'messages'") as cursor:
            assert await cursor.fetchone() is not None
    finally:
        await database.close()


async def test_unknown_operational_error_is_not_retried():
    """Проверяет немедленную передачу неизвестного OperationalError."""
    database = SQLiteDatabase(":memory:")
    await database.open()
    calls = 0

    async def broken(_connection):
        nonlocal calls
        calls += 1
        raise aiosqlite.OperationalError("no such table: missing")

    try:
        with pytest.raises(aiosqlite.OperationalError, match="no such table"):
            await database.write("unknown", broken)
    finally:
        await database.close()

    assert calls == 1


async def test_parallel_save_message_from_many_coroutines():
    """Проверяет 100 конкурентных записей истории."""
    database, history, _ = await _build_persistence(":memory:")
    try:
        await asyncio.gather(
            *(history.save_message(user_id=index, role="user", text=f"message-{index}") for index in range(100))
        )
        async with database.connection.execute("SELECT COUNT(*) FROM messages") as cursor:
            assert (await cursor.fetchone())[0] == 100
    finally:
        await database.close()


async def test_save_message_and_create_exchange_share_write_lock():
    """Проверяет одновременную запись двух persistence-компонентов."""
    database, history, exchange_store = await _build_persistence(":memory:")
    try:
        message_task = history.save_message(user_id=1, role="user", text="message")
        exchange_task = exchange_store.create_exchange(
            initiator_bot_id="anna",
            responder_bot_id="mike",
            topic="topic",
        )
        _, exchange_id = await asyncio.gather(message_task, exchange_task)
        assert await exchange_store.get_exchange(exchange_id) is not None
        assert len(await history.get_history(1)) == 1
        assert history.database is exchange_store.database
        assert history.database.write_lock is exchange_store.database.write_lock
    finally:
        await database.close()


async def test_prune_and_save_message_run_concurrently():
    """Проверяет одновременную очистку и новую запись."""
    database, history, _ = await _build_persistence(":memory:")
    try:
        await database.execute(
            "seed_old_message",
            """
            INSERT INTO messages (user_id, role, text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (1, "user", "old", "2020-01-01 00:00:00"),
        )
        deleted, _ = await asyncio.gather(
            history.prune_older_than(retention_days=30),
            history.save_message(user_id=2, role="user", text="new"),
        )
        assert deleted == 1
        assert [item["text"] for item in await history.get_history(2)] == ["new"]
    finally:
        await database.close()


async def test_read_waits_for_active_write_transaction():
    """Проверяет, что чтение не видит промежуточное состояние write-транзакции."""
    database = SQLiteDatabase(":memory:")
    await database.open()
    await database.execute("create_items", "CREATE TABLE items (value TEXT)")
    write_started = asyncio.Event()
    release_write = asyncio.Event()

    async def delayed_write(connection):
        await connection.execute("INSERT INTO items (value) VALUES ('pending')")
        write_started.set()
        await release_write.wait()

    write_task = asyncio.create_task(database.write("delayed_write", delayed_write))
    await write_started.wait()
    read_task = asyncio.create_task(
        database.fetch_one("count_items", "SELECT COUNT(*) FROM items")
    )
    await asyncio.sleep(0)

    assert not read_task.done()

    release_write.set()
    await write_task
    row = await read_task
    await database.close()

    assert row is not None
    assert row[0] == 1


async def test_runtime_context_closes_shared_database_once():
    """Проверяет, что RuntimeContext закрывает AI client и общую базу."""
    import run

    database = AsyncMock()
    ai_client = AsyncMock()
    context = run.RuntimeContext(
        database=database,
        history=object(),
        prompt_loader=object(),
        ai_client=ai_client,
        topic_selector=object(),
        prompt_composer=object(),
        exchange_store=object(),
    )

    await context.close()

    ai_client.close.assert_awaited_once_with()
    database.close.assert_awaited_once_with()


async def test_runtime_context_build_closes_database_after_partial_failure(monkeypatch):
    """Проверяет cleanup общей базы при ошибке инициализации runtime."""
    import run

    database = AsyncMock()
    monkeypatch.setattr(run, "SQLiteDatabase", lambda _db_path: database)
    monkeypatch.setattr(
        run,
        "MessageHistory",
        lambda _database: type(
            "BrokenHistory",
            (),
            {"init_db": AsyncMock(side_effect=RuntimeError("init failed"))},
        )(),
    )
    settings = type("SettingsStub", (), {"db_path": ":memory:"})()

    with pytest.raises(RuntimeError, match="init failed"):
        await run._build_runtime_context(settings)

    database.open.assert_awaited_once_with()
    database.close.assert_awaited_once_with()
