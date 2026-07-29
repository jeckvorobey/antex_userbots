"""Тесты persisted state для orchestrator."""

from datetime import UTC, datetime, timedelta
import sqlite3

import pytest
import pytest_asyncio

from userbot.exchange_store import ExchangeStore, normalize_signature
from storage.sqlite_database import SQLiteDatabase


@pytest_asyncio.fixture
async def exchange_store():
    """Создаёт in-memory exchange store."""
    database = SQLiteDatabase(":memory:")
    await database.open()
    store = ExchangeStore(database)
    await store.init_db()
    try:
        yield store
    finally:
        await database.close()


def test_normalize_signature_compacts_text():
    """Проверяет нормализацию сигнатуры для anti-repeat."""
    assert normalize_signature("  Один   и тот же   вопрос?! ") == "один и тот же вопрос"


async def test_exchange_store_persists_recent_bot_ids_topics_and_signatures(exchange_store):
    """Проверяет persisted bot/topic/question state для orchestrator."""
    exchange_id = await exchange_store.create_exchange(
        initiator_bot_id="anna",
        responder_bot_id="mike",
        topic="Где есть суп?",
    )
    await exchange_store.mark_exchange_started(exchange_id, initiator_message_id=55, question_signature="Кто знает место с супом?")
    await exchange_store.mark_exchange_completed(exchange_id)

    bot_ids = await exchange_store.get_recent_bot_ids(2)
    topics = await exchange_store.get_recent_topic_keys_by_limit(1)
    signatures = await exchange_store.get_recent_question_signatures(since=timedelta(days=1))

    assert bot_ids == ["mike", "anna"]
    assert "где есть суп" in topics
    assert "кто знает место с супом" in signatures


async def test_exchange_store_returns_recent_unique_bot_ids_by_message_order(exchange_store):
    """Проверяет выбор последних уникальных ботов, которые писали scheduled-сообщения."""
    first_exchange = await exchange_store.create_exchange(
        initiator_bot_id="anna",
        responder_bot_id="mike",
        topic="Первая тема",
    )
    await exchange_store.mark_exchange_started(first_exchange, initiator_message_id=101, question_signature="Первый вопрос")
    await exchange_store.mark_exchange_completed(first_exchange)

    second_exchange = await exchange_store.create_exchange(
        initiator_bot_id="john",
        responder_bot_id="kate",
        topic="Вторая тема",
    )
    await exchange_store.mark_exchange_started(second_exchange, initiator_message_id=102, question_signature="Второй вопрос")
    await exchange_store.mark_exchange_completed(second_exchange)

    third_exchange = await exchange_store.create_exchange(
        initiator_bot_id="lena",
        responder_bot_id="mike",
        topic="Третья тема",
    )
    await exchange_store.mark_exchange_started(third_exchange, initiator_message_id=103, question_signature="Третий вопрос")

    recent_bot_ids = await exchange_store.get_recent_bot_ids(3)

    assert recent_bot_ids == ["lena", "kate", "john"]

    limited_bot_ids = await exchange_store.get_recent_bot_ids(2)

    assert limited_bot_ids == ["lena", "kate"]


async def test_exchange_store_returns_recent_topic_keys_by_limit(exchange_store):
    """Проверяет выбор последних topic_key по количеству, а не по временному окну."""
    for index in range(12):
        exchange_id = await exchange_store.create_exchange(
            initiator_bot_id=f"bot-{index}",
            responder_bot_id=f"responder-{index}",
            topic=f"Тема {index}",
        )
        await exchange_store.mark_exchange_started(
            exchange_id,
            initiator_message_id=index,
            question_signature=f"Вопрос {index}",
        )

    topic_keys = await exchange_store.get_recent_topic_keys_by_limit(10)

    assert topic_keys == {f"тема {index}" for index in range(2, 12)}


async def test_exchange_store_tracks_window_and_due_stages(exchange_store):
    """Проверяет хранение окна и отложенных стадий exchange."""
    exchange_id = await exchange_store.create_exchange(
        initiator_bot_id="anna",
        responder_bot_id="mike",
        topic="Где лучше жить у моря?",
        window_key="2026-04-20T19:10-12",
        initiator_scheduled_at=datetime(2026, 4, 20, 19, 5, tzinfo=UTC),
    )

    planned = await exchange_store.get_exchange_by_window_key("2026-04-20T19:10-12")

    assert planned is not None
    assert planned["exchange_id"] == exchange_id

    await exchange_store.mark_exchange_started(
        exchange_id,
        initiator_message_id=55,
        question_text="Кто где сейчас живёт ближе к морю?",
        question_signature="Кто где сейчас живёт ближе к морю?",
        responder_scheduled_at=datetime(2026, 4, 20, 19, 14, tzinfo=UTC),
    )

    due_started = await exchange_store.get_due_started_exchange(now=datetime(2026, 4, 20, 19, 15, tzinfo=UTC))

    assert due_started is not None
    assert due_started["exchange_id"] == exchange_id
    assert due_started["initiator_message_id"] == 55
    assert due_started["question_text"] == "Кто где сейчас живёт ближе к морю?"


async def test_exchange_store_scopes_queries_by_group(exchange_store):
    """Проверяет изоляцию persisted anti-repeat state между группами."""
    danang_exchange = await exchange_store.create_exchange(
        group_id="danang",
        group_chat_id=-100111,
        initiator_bot_id="anna",
        responder_bot_id="mike",
        topic="Где поесть суп?",
        window_key="2026-04-20T19:19-20",
    )
    await exchange_store.mark_exchange_started(
        danang_exchange,
        initiator_message_id=501,
        question_text="Где суп?",
        question_signature="Где суп?",
        responder_scheduled_at=datetime(2026, 4, 20, 19, 10, tzinfo=UTC),
    )
    await exchange_store.mark_exchange_completed(danang_exchange)

    batumi_exchange = await exchange_store.create_exchange(
        group_id="batumi",
        group_chat_id=-100222,
        initiator_bot_id="kate",
        responder_bot_id="john",
        topic="Где кофе?",
        window_key="2026-04-20T19:19-20",
    )
    await exchange_store.mark_exchange_started(
        batumi_exchange,
        initiator_message_id=601,
        question_text="Где кофе?",
        question_signature="Где кофе?",
        responder_scheduled_at=datetime(2026, 4, 20, 19, 10, tzinfo=UTC),
    )

    assert await exchange_store.get_recent_bot_ids(2, group_id="danang") == ["mike", "anna"]
    assert await exchange_store.get_recent_topic_keys_by_limit(10, group_id="danang") == {"где поесть суп"}
    assert await exchange_store.get_recent_question_signatures(since=timedelta(days=1), group_id="danang") == {"где суп"}
    assert (await exchange_store.get_exchange_by_window_key("2026-04-20T19:19-20", group_id="danang"))["exchange_id"] == danang_exchange
    assert (
        await exchange_store.get_due_started_exchange(now=datetime(2026, 4, 20, 19, 11, tzinfo=UTC), group_id="batumi")
    )["exchange_id"] == batumi_exchange


async def test_exchange_store_migrates_legacy_table_idempotently(tmp_path):
    """Проверяет миграцию старой таблицы без group columns."""
    db_path = tmp_path / "history.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE scheduled_exchanges (
            exchange_id TEXT PRIMARY KEY,
            initiator_bot_id TEXT NOT NULL,
            responder_bot_id TEXT NOT NULL,
            pair_key TEXT NOT NULL,
            window_key TEXT,
            topic TEXT NOT NULL,
            topic_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'planned'
        )
        """
    )
    connection.commit()
    connection.close()

    database = SQLiteDatabase(str(db_path))
    await database.open()
    store = ExchangeStore(database)
    await store.init_db()
    await store.init_db()
    try:
        db = database.connection
        async with db.execute("PRAGMA table_info(scheduled_exchanges)") as cursor:
            rows = await cursor.fetchall()
        columns = [row[1] for row in rows]
    finally:
        await database.close()

    assert "group_id" in columns
    assert "group_chat_id" in columns
    assert "exchange_kind" in columns
    assert "important_scenario" in columns
    assert "last_activity_at" in columns


async def test_exchange_store_creates_indexes_idempotently(exchange_store):
    """Проверяет создание индексов для горячих scheduled exchange запросов."""
    await exchange_store.init_db()
    db = exchange_store.database.connection
    async with db.execute("PRAGMA index_list(scheduled_exchanges)") as cursor:
        rows = await cursor.fetchall()

    index_names = {row[1] for row in rows}

    assert {
        "idx_scheduled_exchanges_group_window_created",
        "idx_scheduled_exchanges_chat_window_created",
        "idx_scheduled_exchanges_group_due_responder",
        "idx_scheduled_exchanges_chat_due_responder",
        "idx_scheduled_exchanges_group_recent_started",
        "idx_scheduled_exchanges_chat_recent_started",
        "idx_scheduled_exchanges_group_recent_completed",
        "idx_scheduled_exchanges_chat_recent_completed",
        "idx_scheduled_exchanges_group_important_recent",
        "idx_scheduled_exchanges_chat_important_recent",
        "idx_scheduled_exchanges_group_activity_recent",
        "idx_scheduled_exchanges_chat_activity_recent",
    }.issubset(index_names)


async def test_exchange_store_backfills_last_activity_for_legacy_rows(tmp_path):
    """Проверяет backfill last_activity_at для старой таблицы."""
    db_path = tmp_path / "history.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE scheduled_exchanges (
            exchange_id TEXT PRIMARY KEY,
            initiator_bot_id TEXT NOT NULL,
            responder_bot_id TEXT NOT NULL,
            pair_key TEXT NOT NULL,
            window_key TEXT,
            topic TEXT NOT NULL,
            topic_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'planned',
            created_at TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        INSERT INTO scheduled_exchanges (
            exchange_id,
            initiator_bot_id,
            responder_bot_id,
            pair_key,
            topic,
            topic_key,
            status,
            created_at,
            started_at,
            completed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "exchange-1",
            "anna",
            "mike",
            "anna->mike",
            "Тема",
            "тема",
            "completed",
            "2026-07-05 10:00:00",
            "2026-07-05 10:05:00",
            "2026-07-05 10:15:00",
        ),
    )
    connection.commit()
    connection.close()

    database = SQLiteDatabase(str(db_path))
    await database.open()
    store = ExchangeStore(database)
    await store.init_db()
    try:
        row = await store.get_exchange("exchange-1")
    finally:
        await database.close()

    assert row is not None
    assert row["last_activity_at"] == "2026-07-05 10:15:00"


async def test_exchange_store_updates_last_activity_on_lifecycle(exchange_store):
    """Проверяет обновление last_activity_at на started/completed стадиях."""
    exchange_id = await exchange_store.create_exchange(
        initiator_bot_id="anna",
        responder_bot_id="mike",
        topic="Тема",
    )
    await exchange_store.mark_exchange_started(
        exchange_id,
        initiator_message_id=101,
        question_signature="Вопрос",
    )

    started = await exchange_store.get_exchange(exchange_id)

    assert started is not None
    assert started["last_activity_at"] == started["started_at"]

    await exchange_store.mark_exchange_completed(exchange_id)
    completed = await exchange_store.get_exchange(exchange_id)

    assert completed is not None
    assert completed["last_activity_at"] == completed["completed_at"]


async def test_exchange_store_persists_exchange_kind_metadata(exchange_store):
    """Проверяет metadata ordinary и important-service exchange."""
    regular_id = await exchange_store.create_exchange(
        initiator_bot_id="anna",
        responder_bot_id="mike",
        topic="Обычная тема",
    )
    important_id = await exchange_store.create_exchange(
        group_id="danang",
        group_chat_id=-100111,
        initiator_bot_id="kate",
        responder_bot_id="john",
        topic="Где можно обменять безналичные рубли?",
        exchange_kind="important_service",
        important_scenario="exchange_rub",
    )

    regular = await exchange_store.get_exchange(regular_id)
    important = await exchange_store.get_exchange(important_id)

    assert regular is not None
    assert regular["exchange_kind"] == "regular"
    assert regular["important_scenario"] is None
    assert important is not None
    assert important["exchange_kind"] == "important_service"
    assert important["important_scenario"] == "exchange_rub"


async def test_exchange_store_returns_latest_important_service_by_group(exchange_store):
    """Проверяет group-scoped latest important-service state."""
    danang_old = await exchange_store.create_exchange(
        group_id="danang",
        group_chat_id=-100111,
        initiator_bot_id="anna",
        responder_bot_id="mike",
        topic="Старый важный вопрос",
        exchange_kind="important_service",
        important_scenario="exchange_rub",
    )
    await exchange_store.mark_exchange_started(danang_old)

    batumi_exchange = await exchange_store.create_exchange(
        group_id="batumi",
        group_chat_id=-100222,
        initiator_bot_id="kate",
        responder_bot_id="john",
        topic="Важный вопрос Батуми",
        exchange_kind="important_service",
        important_scenario="booking_airbnb",
    )
    await exchange_store.mark_exchange_started(batumi_exchange)

    danang_latest = await exchange_store.create_exchange(
        group_id="danang",
        group_chat_id=-100111,
        initiator_bot_id="john",
        responder_bot_id="kate",
        topic="Новый важный вопрос",
        exchange_kind="important_service",
        important_scenario="exchange_usdt",
    )
    await exchange_store.mark_exchange_started(danang_latest)

    latest = await exchange_store.get_latest_important_service_exchange(
        group_id="danang",
        group_chat_id=-100111,
    )

    assert latest is not None
    assert latest["exchange_id"] == danang_latest
    assert latest["important_scenario"] == "exchange_usdt"
    assert latest["group_id"] == "danang"


async def test_exchange_store_recent_queries_use_last_activity_order(exchange_store):
    """Проверяет, что recent context следует last_activity_at."""
    first_exchange = await exchange_store.create_exchange(
        group_id="danang",
        group_chat_id=-100111,
        initiator_bot_id="anna",
        responder_bot_id="mike",
        topic="Первая тема",
    )
    await exchange_store.mark_exchange_started(
        first_exchange,
        question_text="Первый вопрос",
        question_signature="Первый вопрос",
    )
    second_exchange = await exchange_store.create_exchange(
        group_id="danang",
        group_chat_id=-100111,
        initiator_bot_id="kate",
        responder_bot_id="john",
        topic="Вторая тема",
    )
    await exchange_store.mark_exchange_started(
        second_exchange,
        question_text="Второй вопрос",
        question_signature="Второй вопрос",
    )
    db = exchange_store.database.connection
    await db.execute(
        "UPDATE scheduled_exchanges SET last_activity_at = ? WHERE exchange_id = ?",
        ("2026-07-05 10:00:00", first_exchange),
    )
    await db.execute(
        "UPDATE scheduled_exchanges SET last_activity_at = ? WHERE exchange_id = ?",
        ("2026-07-08 10:00:00", second_exchange),
    )
    await db.commit()

    questions = await exchange_store.get_recent_questions(
        since=timedelta(days=3650),
        group_id="danang",
        group_chat_id=-100111,
    )

    assert questions == ["Второй вопрос", "Первый вопрос"]


async def test_exchange_store_prune_older_than_deletes_only_old_rows(exchange_store):
    """Проверяет retention-очистку старых scheduled exchange."""
    db = exchange_store.database.connection
    old_created_at = (datetime.now(UTC) - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
    new_created_at = (datetime.now(UTC) - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    await db.executemany(
        """
        INSERT INTO scheduled_exchanges (
            exchange_id,
            initiator_bot_id,
            responder_bot_id,
            pair_key,
            topic,
            topic_key,
            status,
            created_at,
            last_activity_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("old-exchange", "anna", "mike", "anna:mike", "Старое", "старое", "completed", old_created_at, old_created_at),
            ("new-exchange", "anna", "mike", "anna:mike", "Новое", "новое", "completed", new_created_at, new_created_at),
        ],
    )
    await db.commit()

    deleted = await exchange_store.prune_older_than(retention_days=30)
    row = await exchange_store.get_exchange("new-exchange")
    deleted_row = await exchange_store.get_exchange("old-exchange")

    assert deleted == 1
    assert row is not None
    assert deleted_row is None


async def test_exchange_store_prune_skips_when_retention_disabled(exchange_store):
    """Проверяет отсутствие очистки persisted exchange при retention_days=0."""
    exchange_id = await exchange_store.create_exchange(
        initiator_bot_id="anna",
        responder_bot_id="mike",
        topic="Оставить запись",
    )

    deleted = await exchange_store.prune_older_than(retention_days=0)

    assert deleted == 0
    assert await exchange_store.get_exchange(exchange_id) is not None
