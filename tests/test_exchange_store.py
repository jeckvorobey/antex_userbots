"""Тесты persisted state для orchestrator."""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from userbot.exchange_store import ExchangeStore, normalize_signature


@pytest_asyncio.fixture
async def exchange_store():
    """Создаёт in-memory exchange store."""
    store = ExchangeStore(":memory:")
    await store.init_db()
    try:
        yield store
    finally:
        await store.close()


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
