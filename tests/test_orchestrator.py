"""Тесты swarm-orchestrator."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.runtime_models import SwarmBotProfile
from userbot.orchestrator import IMPORTANT_SERVICE_SCENARIOS, SAFE_SCHEDULED_REPLY_FALLBACK_TEXT, SwarmOrchestrator


def _manager_with_clients(initiator_client, responder_client):
    return SimpleNamespace(
        get_client=lambda bot_id: SimpleNamespace(client=initiator_client if bot_id == "anna" else responder_client),
        scheduled_slot=lambda _bot_id: _ScheduledSlot(True),
    )


@pytest.mark.asyncio
async def test_orchestrator_skips_exchange_when_recent_human_activity_detected():
    """Проверяет отказ от scheduled exchange при недавней активности людей."""
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=SimpleNamespace(get_due_started_exchange=AsyncMock(return_value=None)),
        group_target="@chat",
        skip_if_recent_human_activity=True,
        human_activity_checker=lambda: True,
    )

    assert await orchestrator.run_once() is False


@pytest.mark.asyncio
async def test_orchestrator_skips_exchange_outside_active_windows():
    """Проверяет запрет scheduled exchange вне активных UTC-окон."""
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=SimpleNamespace(get_due_started_exchange=AsyncMock(return_value=None)),
        group_target="@chat",
        active_windows_utc=["10-12"],
        now_provider=lambda: datetime(2026, 4, 20, 13, 0, tzinfo=UTC),
    )

    assert await orchestrator.run_once() is False


@pytest.mark.asyncio
async def test_orchestrator_avoids_recent_bots_and_last_topics():
    """Проверяет anti-repeat по последним ботам и последним темам."""
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_recent_bot_ids=AsyncMock(return_value=["anna", "mike", "john"]),
        get_recent_topic_keys_by_limit=AsyncMock(return_value={"где есть суп"}),
        get_recent_questions=AsyncMock(return_value=[]),
    )
    topic_selector = SimpleNamespace(topics=["Где есть суп", "Куда сходить вечером"])
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
            SwarmBotProfile(id="john", session_string="john", persona_file="john.md", telegram_user_id=303),
            SwarmBotProfile(id="kate", session_string="kate", persona_file="kate.md", telegram_user_id=404),
            SwarmBotProfile(id="lena", session_string="lena", persona_file="lena.md", telegram_user_id=505),
        ],
        manager=SimpleNamespace(),
        topic_selector=topic_selector,
        prompt_composer=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=exchange_store,
    )

    decision = await orchestrator._build_exchange_decision()

    assert {decision.initiator.id, decision.responder.id} == {"kate", "lena"}
    assert decision.topic == "Куда сходить вечером"


@pytest.mark.asyncio
async def test_orchestrator_relaxes_recent_bot_filter_when_pool_is_too_small():
    """Проверяет fallback, если после исключения последних 3 ботов не хватает пары."""
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_recent_bot_ids=AsyncMock(return_value=["anna", "mike", "john"]),
        get_recent_topic_keys_by_limit=AsyncMock(return_value=set()),
        get_recent_questions=AsyncMock(return_value=[]),
    )
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
            SwarmBotProfile(id="john", session_string="john", persona_file="john.md", telegram_user_id=303),
        ],
        manager=SimpleNamespace(),
        topic_selector=SimpleNamespace(topics=["Тема"]),
        prompt_composer=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=exchange_store,
    )

    decision = await orchestrator._build_exchange_decision()

    assert decision.initiator.id != decision.responder.id


@pytest.mark.asyncio
async def test_orchestrator_regenerates_repeated_question_signature():
    """Проверяет повторную генерацию вопроса при совпадении recent signature."""
    gemini = SimpleNamespace(start_topic=AsyncMock(side_effect=["Один и тот же вопрос?", "Другой вопрос?"]))
    exchange_store = SimpleNamespace(get_recent_question_signatures=AsyncMock(return_value={"один и тот же вопрос"}))
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        gemini_client=gemini,
        history=SimpleNamespace(),
        exchange_store=exchange_store,
    )

    question = await orchestrator._generate_non_repeating_question(initiator_prompt="prompt", topic="Тема")

    assert question == "Другой вопрос?"
    assert gemini.start_topic.await_count == 2


@pytest.mark.asyncio
async def test_orchestrator_runs_exchange_and_saves_history():
    """Проверяет двухфазный scheduled exchange с отложенным ответом."""
    initiator_client = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(id=501)))
    responder_client = SimpleNamespace(send_message=AsyncMock())
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_exchange_by_window_key=AsyncMock(return_value=None),
        get_recent_bot_ids=AsyncMock(return_value=[]),
        get_recent_topic_keys_by_limit=AsyncMock(return_value=set()),
        get_recent_questions=AsyncMock(return_value=[]),
        get_recent_question_signatures=AsyncMock(return_value=set()),
        create_exchange=AsyncMock(return_value="exchange-1"),
        mark_exchange_started=AsyncMock(),
        mark_exchange_completed=AsyncMock(),
    )
    history = SimpleNamespace(
        get_session_history=AsyncMock(return_value=[]),
        save_message=AsyncMock(),
    )

    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=_manager_with_clients(initiator_client, responder_client),
        topic_selector=SimpleNamespace(topics=["Где поесть суп?"]),
        prompt_composer=SimpleNamespace(compose=AsyncMock(side_effect=["system-init", "system-reply"])),
        gemini_client=SimpleNamespace(
            start_topic=AsyncMock(return_value="Кто знает место с хорошим супом?"),
            generate_reply=AsyncMock(return_value="Мне нравится Pho 54."),
        ),
        history=history,
        exchange_store=exchange_store,
        group_target="@chat",
        question_repeat_window=timedelta(days=2),
        active_windows_utc=["19-20"],
        now_provider=lambda: datetime(2026, 4, 20, 19, 5, tzinfo=UTC),
        randint_provider=lambda start, end: start,
        responder_delay_minutes=(8, 8),
    )
    orchestrator._build_exchange_decision = AsyncMock(
        return_value=SimpleNamespace(
            initiator=orchestrator.bot_profiles[0],
            responder=orchestrator.bot_profiles[1],
            topic="Где поесть суп?",
            topic_key="где поесть суп",
            recent_questions=[],
        )
    )

    started = await orchestrator.run_once()

    assert started is True
    initiator_client.send_message.assert_awaited_once_with("@chat", "Кто знает место с хорошим супом?")
    responder_client.send_message.assert_not_awaited()
    exchange_store.mark_exchange_started.assert_awaited_once()
    exchange_store.mark_exchange_completed.assert_not_awaited()
    assert history.save_message.await_count == 1
    assert history.save_message.await_args_list[0].kwargs["message_origin"] == "scheduled_initiator"
    assert history.save_message.await_args_list[0].kwargs["exchange_id"] == "exchange-1"
    assert exchange_store.mark_exchange_started.await_args.kwargs["responder_scheduled_at"] == datetime(
        2026,
        4,
        20,
        19,
        13,
        tzinfo=UTC,
    )


@pytest.mark.asyncio
async def test_orchestrator_uses_local_fallback_when_scheduled_llm_disabled():
    """Проверяет локальный fallback для initiator без вызова Gemini."""
    initiator_client = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(id=501)))
    responder_client = SimpleNamespace(send_message=AsyncMock())
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_exchange_by_window_key=AsyncMock(return_value=None),
        get_recent_bot_ids=AsyncMock(return_value=[]),
        get_recent_topic_keys_by_limit=AsyncMock(return_value=set()),
        get_recent_questions=AsyncMock(return_value=[]),
        create_exchange=AsyncMock(return_value="exchange-1"),
        mark_exchange_started=AsyncMock(),
        mark_exchange_completed=AsyncMock(),
    )
    gemini_client = SimpleNamespace(
        start_topic=AsyncMock(return_value="Небезопасный вопрос?"),
        generate_reply=AsyncMock(),
        is_output_safe=lambda text: True,
    )
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=_manager_with_clients(initiator_client, responder_client),
        topic_selector=SimpleNamespace(topics=["Где поесть суп"]),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system-init")),
        gemini_client=gemini_client,
        history=SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock()),
        exchange_store=exchange_store,
        group_target="@chat",
        allow_external_llm_for_scheduled=False,
        active_windows_utc=["19-20"],
        now_provider=lambda: datetime(2026, 4, 20, 19, 5, tzinfo=UTC),
        randint_provider=lambda start, end: start,
    )
    orchestrator._build_exchange_decision = AsyncMock(
        return_value=SimpleNamespace(
            initiator=orchestrator.bot_profiles[0],
            responder=orchestrator.bot_profiles[1],
            topic="Где поесть суп",
            topic_key="где поесть суп",
            recent_questions=[],
        )
    )

    started = await orchestrator.run_once()

    assert started is True
    gemini_client.start_topic.assert_not_awaited()
    initiator_client.send_message.assert_awaited_once_with("@chat", "Кто может подсказать: где поесть суп?")


@pytest.mark.asyncio
async def test_orchestrator_replaces_unsafe_responder_output_with_fallback():
    """Проверяет safety-gate для scheduled responder."""
    initiator_client = SimpleNamespace(send_message=AsyncMock())
    responder_client = SimpleNamespace(send_message=AsyncMock())
    exchange_store = SimpleNamespace(
        mark_exchange_completed=AsyncMock(),
    )
    history = SimpleNamespace(
        get_session_history=AsyncMock(return_value=[]),
        save_message=AsyncMock(),
    )
    gemini_client = SimpleNamespace(
        generate_reply=AsyncMock(return_value="https://t.me/+secret"),
        is_output_safe=lambda text: False,
    )
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=_manager_with_clients(initiator_client, responder_client),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system-reply")),
        gemini_client=gemini_client,
        history=history,
        exchange_store=exchange_store,
        group_target="@chat",
    )

    started = await orchestrator._run_due_responder_exchange(
        exchange={
            "exchange_id": "exchange-1",
            "initiator_bot_id": "anna",
            "responder_bot_id": "mike",
            "topic": "Где поесть суп",
            "question_text": "Кто знает место с хорошим супом?",
            "initiator_message_id": 501,
        }
    )

    assert started is True
    responder_client.send_message.assert_awaited_once_with("@chat", SAFE_SCHEDULED_REPLY_FALLBACK_TEXT, reply_to=501)
    history.save_message.assert_awaited_once()
    assert history.save_message.await_args.kwargs["text"] == SAFE_SCHEDULED_REPLY_FALLBACK_TEXT


@pytest.mark.asyncio
async def test_orchestrator_scopes_exchange_to_group_and_uses_real_chat_id():
    """Проверяет group scope для scheduled exchange."""
    initiator_client = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(id=501)))
    responder_client = SimpleNamespace(send_message=AsyncMock())
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_exchange_by_window_key=AsyncMock(return_value=None),
        get_recent_bot_ids=AsyncMock(return_value=[]),
        get_recent_topic_keys_by_limit=AsyncMock(return_value=set()),
        get_recent_questions=AsyncMock(return_value=[]),
        get_recent_question_signatures=AsyncMock(return_value=set()),
        create_exchange=AsyncMock(return_value="exchange-1"),
        mark_exchange_started=AsyncMock(),
        mark_exchange_completed=AsyncMock(),
    )
    history = SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock())
    prompt_composer = SimpleNamespace(compose=AsyncMock(return_value="system-init"))

    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=_manager_with_clients(initiator_client, responder_client),
        topic_selector=SimpleNamespace(topics=["Где поесть суп?"]),
        prompt_composer=prompt_composer,
        gemini_client=SimpleNamespace(start_topic=AsyncMock(return_value="Кто знает место с хорошим супом?")),
        history=history,
        exchange_store=exchange_store,
        group_id="danang",
        group_city="Da Nang",
        group_target="@danang",
        group_chat_id=-100111,
        active_windows_utc=["19-20"],
        now_provider=lambda: datetime(2026, 4, 20, 19, 5, tzinfo=UTC),
        randint_provider=lambda start, end: start,
    )
    orchestrator._build_exchange_decision = AsyncMock(
        return_value=SimpleNamespace(
            initiator=orchestrator.bot_profiles[0],
            responder=orchestrator.bot_profiles[1],
            topic="Где поесть суп?",
            topic_key="где поесть суп",
            recent_questions=[],
        )
    )

    assert await orchestrator.run_once() is True

    exchange_store.get_due_started_exchange.assert_awaited_once_with(
        now=datetime(2026, 4, 20, 19, 5, tzinfo=UTC),
        group_id="danang",
        group_chat_id=-100111,
    )
    exchange_store.get_exchange_by_window_key.assert_awaited_once_with(
        "2026-04-20T19:19-20",
        group_id="danang",
        group_chat_id=-100111,
    )
    exchange_store.create_exchange.assert_awaited_once()
    assert exchange_store.create_exchange.await_args.kwargs["group_id"] == "danang"
    assert exchange_store.create_exchange.await_args.kwargs["group_chat_id"] == -100111
    assert history.save_message.await_args.kwargs["chat_id"] == -100111
    assert "город: Da Nang" in prompt_composer.compose.await_args.kwargs["exchange_context"]


@pytest.mark.asyncio
async def test_orchestrator_sends_due_responder_and_completes_exchange():
    """Проверяет, что ответчик отвечает только после наступления due времени."""
    initiator_client = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(id=501)))
    responder_client = SimpleNamespace(send_message=AsyncMock())
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(
            return_value={
                "exchange_id": "exchange-1",
                "initiator_bot_id": "anna",
                "responder_bot_id": "mike",
                "topic": "Где поесть суп?",
                "question_text": "Кто знает место с хорошим супом?",
                "initiator_message_id": 501,
            }
        ),
        get_exchange_by_window_key=AsyncMock(),
        mark_exchange_completed=AsyncMock(),
    )
    history = SimpleNamespace(
        get_session_history=AsyncMock(return_value=[]),
        save_message=AsyncMock(),
    )

    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=_manager_with_clients(initiator_client, responder_client),
        topic_selector=SimpleNamespace(topics=["Где поесть суп?"]),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system-reply")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock(return_value="Мне нравится Pho 54.")),
        history=history,
        exchange_store=exchange_store,
        group_target="@chat",
        now_provider=lambda: datetime(2026, 4, 20, 19, 14, tzinfo=UTC),
    )

    started = await orchestrator.run_once()

    assert started is True
    responder_client.send_message.assert_awaited_once_with("@chat", "Мне нравится Pho 54.", reply_to=501)
    exchange_store.mark_exchange_completed.assert_awaited_once_with("exchange-1")
    assert history.save_message.await_count == 1
    assert history.save_message.await_args.kwargs["message_origin"] == "scheduled_responder"


@pytest.mark.asyncio
async def test_orchestrator_creates_only_one_exchange_per_window():
    """Проверяет, что в одном активном окне не создаётся второй exchange."""
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_exchange_by_window_key=AsyncMock(
            return_value={
                "exchange_id": "exchange-1",
                "status": "completed",
            }
        ),
        create_exchange=AsyncMock(),
    )
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=exchange_store,
        group_target="@chat",
        active_windows_utc=["19-20"],
        now_provider=lambda: datetime(2026, 4, 20, 19, 10, tzinfo=UTC),
    )

    started = await orchestrator.run_once()

    assert started is False
    exchange_store.create_exchange.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_important_service_cadence_uses_utc_calendar_days():
    """Проверяет, что важный вопрос после 5 июля снова доступен только 8 июля."""
    orchestrator = SwarmOrchestrator(
        bot_profiles=[],
        manager=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=SimpleNamespace(),
        now_provider=lambda: datetime(2026, 7, 7, 10, 0, tzinfo=UTC),
    )
    latest = {"started_at": "2026-07-05 18:00:00", "created_at": "2026-07-05 18:00:00"}

    assert orchestrator._important_service_is_due(latest, datetime(2026, 7, 7, 10, 0, tzinfo=UTC)) is False
    assert orchestrator._important_service_is_due(latest, datetime(2026, 7, 8, 10, 0, tzinfo=UTC)) is True


def test_orchestrator_rotates_important_service_scenarios():
    """Проверяет фиксированную очередь important-service сценариев."""
    orchestrator = SwarmOrchestrator(
        bot_profiles=[],
        manager=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=SimpleNamespace(),
    )

    assert orchestrator._next_important_service_scenario(None).key == "exchange_rub"
    assert orchestrator._next_important_service_scenario("exchange_rub").key == "booking_airbnb"
    assert orchestrator._next_important_service_scenario("booking_airbnb").key == "exchange_usdt"
    assert orchestrator._next_important_service_scenario("exchange_usdt").key == "booking_booking"
    assert orchestrator._next_important_service_scenario("booking_booking").key == "exchange_rub"


@pytest.mark.asyncio
async def test_orchestrator_important_service_replaces_regular_topic_when_due():
    """Проверяет, что due important-service exchange подменяет обычную тему окна."""
    initiator_client = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(id=701)))
    responder_client = SimpleNamespace(send_message=AsyncMock())
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_exchange_by_window_key=AsyncMock(return_value=None),
        get_latest_important_service_exchange=AsyncMock(return_value=None),
        get_recent_bot_ids=AsyncMock(return_value=[]),
        get_recent_questions=AsyncMock(return_value=[]),
        get_recent_question_signatures=AsyncMock(return_value=set()),
        create_exchange=AsyncMock(return_value="exchange-important"),
        mark_exchange_started=AsyncMock(),
        mark_exchange_completed=AsyncMock(),
    )
    prompt_composer = SimpleNamespace(compose=AsyncMock(return_value="system-init"))
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=_manager_with_clients(initiator_client, responder_client),
        topic_selector=SimpleNamespace(topics=["Обычная тема"]),
        prompt_composer=prompt_composer,
        gemini_client=SimpleNamespace(start_topic=AsyncMock(return_value="Где сейчас нормально поменять безналичные рубли?")),
        history=SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock()),
        exchange_store=exchange_store,
        group_id="danang",
        group_city="Da Nang",
        group_target="@danang",
        group_chat_id=-100111,
        active_windows_utc=["10-11"],
        now_provider=lambda: datetime(2026, 7, 8, 10, 15, tzinfo=UTC),
        randint_provider=lambda start, end: start,
    )

    assert await orchestrator.run_once() is True

    exchange_store.get_latest_important_service_exchange.assert_awaited_once_with(
        group_id="danang",
        group_chat_id=-100111,
    )
    exchange_store.create_exchange.assert_awaited_once()
    assert exchange_store.create_exchange.await_args.kwargs["exchange_kind"] == "important_service"
    assert exchange_store.create_exchange.await_args.kwargs["important_scenario"] == "exchange_rub"
    assert "important_service_question" in prompt_composer.compose.await_args.kwargs["exchange_context"]
    assert "@tt_exchenge_bot" in prompt_composer.compose.await_args.kwargs["exchange_context"]


@pytest.mark.asyncio
async def test_orchestrator_reselects_topic_when_initiator_recent_history_matches(monkeypatch):
    """Проверяет, что bot-history заставляет выбрать другой topic из остатка пула."""
    initiator_client = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(id=801)))
    responder_client = SimpleNamespace(send_message=AsyncMock())
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_exchange_by_window_key=AsyncMock(return_value=None),
        get_recent_bot_ids=AsyncMock(return_value=[]),
        get_recent_topic_keys_by_limit=AsyncMock(return_value=set()),
        get_recent_questions=AsyncMock(return_value=[]),
        get_recent_question_signatures=AsyncMock(return_value=set()),
        create_exchange=AsyncMock(return_value="exchange-2"),
        mark_exchange_started=AsyncMock(),
        mark_exchange_completed=AsyncMock(),
    )
    history = SimpleNamespace(
        get_session_history=AsyncMock(
            return_value=[
                {
                    "role": "assistant",
                    "text": "Старый вопрос?",
                    "message_origin": "scheduled_initiator",
                }
            ]
        ),
        save_message=AsyncMock(),
    )
    monkeypatch.setattr("userbot.orchestrator.random.choice", lambda seq: seq[-1])

    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=_manager_with_clients(initiator_client, responder_client),
        topic_selector=SimpleNamespace(topics=["Старый вопрос?", "Другой вопрос?"]),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system-init")),
        gemini_client=SimpleNamespace(
            start_topic=AsyncMock(side_effect=["Старый вопрос?", "Новый вопрос?"]),
        ),
        history=history,
        exchange_store=exchange_store,
        group_id="danang",
        group_city="Da Nang",
        group_target="@danang",
        group_chat_id=-100111,
        active_windows_utc=["19-20"],
        now_provider=lambda: datetime(2026, 4, 20, 19, 5, tzinfo=UTC),
        randint_provider=lambda start, end: start,
    )
    orchestrator._build_exchange_decision = AsyncMock(
        return_value=SimpleNamespace(
            initiator=orchestrator.bot_profiles[0],
            responder=orchestrator.bot_profiles[1],
            topic="Старый вопрос?",
            topic_key="старый вопрос",
            recent_questions=[],
        )
    )

    assert await orchestrator.run_once() is True

    assert history.get_session_history.await_args.kwargs["chat_id"] == -100111
    assert history.get_session_history.await_args.kwargs["bot_id"] == "anna"
    assert history.get_session_history.await_args.kwargs["limit"] == 50
    assert orchestrator.gemini_client.start_topic.await_count == 2
    assert orchestrator.gemini_client.start_topic.await_args_list[0].kwargs["topic"] == "Старый вопрос?"
    assert orchestrator.gemini_client.start_topic.await_args_list[1].kwargs["topic"] == "Другой вопрос?"
    assert history.save_message.await_args.kwargs["text"] == "Новый вопрос?"


@pytest.mark.asyncio
async def test_orchestrator_important_service_respects_existing_window_exchange():
    """Проверяет, что important-service не создаёт второй exchange в занятом окне."""
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_exchange_by_window_key=AsyncMock(return_value={"exchange_id": "regular", "status": "completed"}),
        get_latest_important_service_exchange=AsyncMock(return_value=None),
        create_exchange=AsyncMock(),
    )
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=exchange_store,
        group_target="@chat",
        active_windows_utc=["10-11"],
        now_provider=lambda: datetime(2026, 7, 8, 10, 15, tzinfo=UTC),
    )

    assert await orchestrator.run_once() is False
    exchange_store.get_latest_important_service_exchange.assert_not_called()
    exchange_store.create_exchange.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_important_service_respects_human_activity_gate():
    """Проверяет, что important-service использует общий human-activity gate."""
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_latest_important_service_exchange=AsyncMock(return_value=None),
        create_exchange=AsyncMock(),
    )
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=exchange_store,
        group_target="@chat",
        active_windows_utc=["10-11"],
        now_provider=lambda: datetime(2026, 7, 8, 10, 15, tzinfo=UTC),
        skip_if_recent_human_activity=True,
        human_activity_checker=lambda: True,
    )

    assert await orchestrator.run_once() is False
    exchange_store.get_latest_important_service_exchange.assert_not_called()
    exchange_store.create_exchange.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_important_service_reply_context_mentions_required_contact():
    """Проверяет prompt-context ответа для important-service exchange."""
    initiator_client = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(id=501)))
    responder_client = SimpleNamespace(send_message=AsyncMock())
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(
            return_value={
                "exchange_id": "exchange-important",
                "initiator_bot_id": "anna",
                "responder_bot_id": "mike",
                "topic": IMPORTANT_SERVICE_SCENARIOS[0].question_intent,
                "question_text": "Где можно обменять безналичные рубли?",
                "initiator_message_id": 501,
                "exchange_kind": "important_service",
                "important_scenario": "exchange_rub",
            }
        ),
        mark_exchange_completed=AsyncMock(),
    )
    prompt_composer = SimpleNamespace(compose=AsyncMock(return_value="system-reply"))
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=_manager_with_clients(initiator_client, responder_client),
        topic_selector=SimpleNamespace(),
        prompt_composer=prompt_composer,
        gemini_client=SimpleNamespace(generate_reply=AsyncMock(return_value="Я бы написал в @tt_exchenge_bot.")),
        history=SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock()),
        exchange_store=exchange_store,
        group_target="@chat",
        now_provider=lambda: datetime(2026, 7, 8, 10, 20, tzinfo=UTC),
    )

    assert await orchestrator.run_once() is True

    context = prompt_composer.compose.await_args.kwargs["exchange_context"]
    assert "important_service_answer" in context
    assert "exchange_rub" in context
    assert "@tt_exchenge_bot" in context
    assert "Обратись в сервис" in context


@pytest.mark.asyncio
async def test_orchestrator_resolves_group_target_per_sending_client():
    """Проверяет отдельный резолв entity группы для отправителя вопроса."""
    initiator_client = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(id=501)))
    responder_client = SimpleNamespace(send_message=AsyncMock())
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_exchange_by_window_key=AsyncMock(return_value=None),
        get_recent_bot_ids=AsyncMock(return_value=[]),
        get_recent_topic_keys_by_limit=AsyncMock(return_value=set()),
        get_recent_questions=AsyncMock(return_value=[]),
        get_recent_question_signatures=AsyncMock(return_value=set()),
        create_exchange=AsyncMock(return_value="exchange-1"),
        mark_exchange_started=AsyncMock(),
        mark_exchange_completed=AsyncMock(),
    )
    history = SimpleNamespace(
        get_session_history=AsyncMock(return_value=[]),
        save_message=AsyncMock(),
    )
    resolved_targets: list[object] = [object(), object()]
    resolve_group_target = AsyncMock(side_effect=resolved_targets)

    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=_manager_with_clients(initiator_client, responder_client),
        topic_selector=SimpleNamespace(topics=["Где поесть суп?"]),
        prompt_composer=SimpleNamespace(compose=AsyncMock(side_effect=["system-init", "system-reply"])),
        gemini_client=SimpleNamespace(
            start_topic=AsyncMock(return_value="Кто знает место с хорошим супом?"),
            generate_reply=AsyncMock(return_value="Мне нравится Pho 54."),
        ),
        history=history,
        exchange_store=exchange_store,
        group_target="@chat",
        group_chat_id=-100123,
        resolve_group_target=resolve_group_target,
    )
    orchestrator._build_exchange_decision = AsyncMock(
        return_value=SimpleNamespace(
            initiator=orchestrator.bot_profiles[0],
            responder=orchestrator.bot_profiles[1],
            topic="Где поесть суп?",
            topic_key="где поесть суп",
            recent_questions=[],
        )
    )

    started = await orchestrator.run_once()

    assert started is True
    assert resolve_group_target.await_count == 1
    initiator_client.send_message.assert_awaited_once_with(resolved_targets[0], "Кто знает место с хорошим супом?")
    responder_client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_orchestrator_skips_when_bot_is_busy():
    """Проверяет, что planned exchange не стартует, если инициатор занят."""
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_exchange_by_window_key=AsyncMock(return_value=None),
        get_recent_bot_ids=AsyncMock(return_value=[]),
        get_recent_topic_keys_by_limit=AsyncMock(return_value=set()),
        get_recent_questions=AsyncMock(return_value=[]),
        get_recent_question_signatures=AsyncMock(return_value=set()),
        create_exchange=AsyncMock(return_value="exchange-1"),
    )
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=SimpleNamespace(
            scheduled_slot=lambda bot_id: _ScheduledSlot(bot_id != "anna"),
            get_client=lambda _bot_id: None,
        ),
        topic_selector=SimpleNamespace(topics=["Тема"]),
        prompt_composer=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=exchange_store,
        group_target="@chat",
        active_windows_utc=["19-20"],
        now_provider=lambda: datetime(2026, 4, 20, 19, 5, tzinfo=UTC),
        initiator_offset_minutes=(5, 5),
    )
    orchestrator._build_exchange_decision = AsyncMock(
        return_value=SimpleNamespace(
            initiator=orchestrator.bot_profiles[0],
            responder=orchestrator.bot_profiles[1],
            topic="Тема",
            topic_key="тема",
            recent_questions=[],
        )
    )

    assert await orchestrator.run_once() is False
    exchange_store.create_exchange.assert_awaited_once()


def test_orchestrator_picks_initiator_due_at_inside_remaining_active_window():
    """Проверяет, что старт инициатора выбирается внутри остатка активного окна."""
    orchestrator = SwarmOrchestrator(
        bot_profiles=[],
        manager=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        gemini_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=SimpleNamespace(),
        active_windows_utc=["3-7"],
        now_provider=lambda: datetime(2026, 4, 20, 5, 0, tzinfo=UTC),
        randint_provider=lambda start, end: 60,
    )

    due_at = orchestrator._pick_initiator_due_at(
        window_start=datetime(2026, 4, 20, 3, 0, tzinfo=UTC),
        window_end=datetime(2026, 4, 20, 7, 0, tzinfo=UTC),
    )

    assert due_at == datetime(2026, 4, 20, 5, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_orchestrator_uses_second_precision_for_responder_due_time():
    """Проверяет, что задержка ответа выбирается с точностью до секунд."""
    initiator_client = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(id=501)))
    responder_client = SimpleNamespace(send_message=AsyncMock())
    exchange_store = SimpleNamespace(
        get_due_started_exchange=AsyncMock(return_value=None),
        get_exchange_by_window_key=AsyncMock(return_value=None),
        get_recent_bot_ids=AsyncMock(return_value=[]),
        get_recent_topic_keys_by_limit=AsyncMock(return_value=set()),
        get_recent_questions=AsyncMock(return_value=[]),
        get_recent_question_signatures=AsyncMock(return_value=set()),
        create_exchange=AsyncMock(return_value="exchange-1"),
        mark_exchange_started=AsyncMock(),
        mark_exchange_completed=AsyncMock(),
    )
    history = SimpleNamespace(
        get_session_history=AsyncMock(return_value=[]),
        save_message=AsyncMock(),
    )

    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=_manager_with_clients(initiator_client, responder_client),
        topic_selector=SimpleNamespace(topics=["Где поесть суп?"]),
        prompt_composer=SimpleNamespace(compose=AsyncMock(side_effect=["system-init", "system-reply"])),
        gemini_client=SimpleNamespace(
            start_topic=AsyncMock(return_value="Кто знает место с хорошим супом?"),
            generate_reply=AsyncMock(return_value="Мне нравится Pho 54."),
        ),
        history=history,
        exchange_store=exchange_store,
        group_target="@chat",
        question_repeat_window=timedelta(days=2),
        active_windows_utc=["19-20"],
        now_provider=lambda: datetime(2026, 4, 20, 19, 5, tzinfo=UTC),
        randint_provider=lambda start, end: 0 if start == 0 else 85,
        responder_delay_minutes=(1, 3),
    )
    orchestrator._build_exchange_decision = AsyncMock(
        return_value=SimpleNamespace(
            initiator=orchestrator.bot_profiles[0],
            responder=orchestrator.bot_profiles[1],
            topic="Где поесть суп?",
            topic_key="где поесть суп",
            recent_questions=[],
        )
    )

    started = await orchestrator.run_once()

    assert started is True
    assert exchange_store.mark_exchange_started.await_args.kwargs["responder_scheduled_at"] == datetime(
        2026,
        4,
        20,
        19,
        6,
        25,
        tzinfo=UTC,
    )


class _ScheduledSlot:
    """Управляемый async context manager для scheduled slot."""

    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired

    async def __aenter__(self):
        return self.acquired

    async def __aexit__(self, exc_type, exc, tb):
        return False
