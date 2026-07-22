"""Тесты адресного reply-router для swarm-режима."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.runtime_models import SwarmBotProfile
import userbot.reply_router as reply_router
from userbot.reply_router import AddressedReplyRouter, SAFE_REPLY_FALLBACK_TEXT, _ReplyRateLimiter


@pytest.fixture(autouse=True)
def _replace_addressed_reply_delay(monkeypatch):
    """Исключает реальное четырёхминутное ожидание из unit-тестов router-а."""
    monkeypatch.setattr(reply_router, "asyncio", SimpleNamespace(sleep=AsyncMock()), raising=False)


def _build_event(
    *,
    sender_id: int,
    raw_text: str = "Привет",
    is_reply: bool = True,
    reply_sender_id: int | None = 101,
    reply_message_id: int = 55,
    sender_is_bot: bool = False,
    chat_id: int = -100555,
):
    reply_message = SimpleNamespace(sender_id=reply_sender_id, id=reply_message_id)
    return SimpleNamespace(
        sender_id=sender_id,
        raw_text=raw_text,
        is_reply=is_reply,
        chat_id=chat_id,
        id=77,
        reply=AsyncMock(),
        get_reply_message=AsyncMock(return_value=reply_message if is_reply else None),
        get_sender=AsyncMock(return_value=SimpleNamespace(bot=sender_is_bot)),
    )


@pytest.mark.asyncio
async def test_router_ignores_non_reply_message():
    """Проверяет, что router игнорирует обычные сообщения без reply."""
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=SimpleNamespace(get_session_history=AsyncMock(), save_message=AsyncMock()),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock()),
        swarm_user_ids={202, 303},
    )

    handled = await router.handle_event(_build_event(sender_id=999, is_reply=False))

    assert handled is False


@pytest.mark.asyncio
async def test_router_ignores_event_outside_enabled_groups():
    """Проверяет, что router отвечает только в enabled configured groups."""
    history = SimpleNamespace(get_session_history=AsyncMock(), save_message=AsyncMock())
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=history,
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock()),
        swarm_user_ids={202, 303},
        enabled_group_chat_ids={-100555},
    )

    handled = await router.handle_event(_build_event(sender_id=999, chat_id=-100999))

    assert handled is False
    history.get_session_history.assert_not_called()


@pytest.mark.asyncio
async def test_router_ignores_reply_to_another_bot():
    """Проверяет, что бот не отвечает на reply к сообщению другого swarm-бота."""
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=SimpleNamespace(get_session_history=AsyncMock(), save_message=AsyncMock()),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock()),
        swarm_user_ids={202, 303},
    )

    handled = await router.handle_event(_build_event(sender_id=999, reply_sender_id=202))

    assert handled is False


@pytest.mark.asyncio
async def test_router_ignores_messages_from_swarm_bot():
    """Проверяет, что router игнорирует входящее сообщение от другого swarm-бота."""
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=SimpleNamespace(get_session_history=AsyncMock(), save_message=AsyncMock()),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock()),
        swarm_user_ids={202, 303},
    )

    handled = await router.handle_event(_build_event(sender_id=202, reply_sender_id=101))

    assert handled is False


@pytest.mark.asyncio
async def test_router_ignores_reply_from_telegram_bot_sender():
    """Проверяет, что бот не отвечает на reply от Telegram-бота."""
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=SimpleNamespace(get_session_history=AsyncMock(), save_message=AsyncMock()),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock()),
        swarm_user_ids={202, 303},
    )

    handled = await router.handle_event(_build_event(sender_id=999, reply_sender_id=101, sender_is_bot=True))

    assert handled is False


@pytest.mark.asyncio
async def test_router_answers_only_to_addressed_bot_and_saves_history():
    """Проверяет генерацию ответа адресованным ботом и сохранение swarm-метаданных."""
    history = SimpleNamespace(
        get_session_history=AsyncMock(return_value=[{"role": "user", "text": "Предыдущее"}]),
        save_message=AsyncMock(),
    )
    prompt_composer = SimpleNamespace(compose=AsyncMock(return_value="system+persona"))
    gemini_client = SimpleNamespace(generate_reply=AsyncMock(return_value="Ответ Анны"))
    manager = SimpleNamespace(human_slot=lambda _bot_id: _AsyncNullContext())

    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=history,
        prompt_composer=prompt_composer,
        gemini_client=gemini_client,
        swarm_user_ids={202, 303},
        manager=manager,
    )

    event = _build_event(sender_id=999, raw_text="Как думаешь?")

    handled = await router.handle_event(event)

    assert handled is True
    prompt_composer.compose.assert_awaited_once_with("reply", bot_id="anna", persona_file="anna.md")
    gemini_client.generate_reply.assert_awaited_once_with(
        system_prompt="system+persona",
        history=[{"role": "user", "text": "Предыдущее"}],
        user_message="Как думаешь?",
    )
    event.reply.assert_awaited_once_with("Ответ Анны")
    assert history.save_message.await_count == 2
    assert history.save_message.await_args_list[0].kwargs["message_origin"] == "human_reply"
    assert history.save_message.await_args_list[1].kwargs["bot_id"] == "anna"


@pytest.mark.asyncio
async def test_router_waits_four_minutes_before_sending_addressed_reply(monkeypatch):
    """Проверяет обязательную задержку перед публикацией адресного ответа."""
    sleep = AsyncMock()
    monkeypatch.setattr(reply_router, "asyncio", SimpleNamespace(sleep=sleep), raising=False)
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock()),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system+persona")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock(return_value="Ответ Анны")),
        swarm_user_ids={202, 303},
    )
    event = _build_event(sender_id=999)

    handled = await router.handle_event(event)

    assert handled is True
    sleep.assert_awaited_once_with(240)
    event.reply.assert_awaited_once_with("Ответ Анны")


@pytest.mark.asyncio
async def test_router_uses_safe_fallback_when_external_llm_disabled():
    """Проверяет локальный fallback без обращения к Gemini."""
    history = SimpleNamespace(
        get_session_history=AsyncMock(return_value=[]),
        save_message=AsyncMock(),
    )
    gemini_client = SimpleNamespace(generate_reply=AsyncMock(return_value="Ответ Анны"))
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=history,
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system+persona")),
        gemini_client=gemini_client,
        swarm_user_ids={202, 303},
        manager=SimpleNamespace(human_slot=lambda _bot_id: _AsyncNullContext()),
        security_settings_getter=lambda: SimpleNamespace(swarm_allow_external_llm_for_replies=False),
    )

    event = _build_event(sender_id=999, raw_text="Как думаешь?")

    handled = await router.handle_event(event)

    assert handled is True
    gemini_client.generate_reply.assert_not_awaited()
    event.reply.assert_awaited_once_with(SAFE_REPLY_FALLBACK_TEXT)


@pytest.mark.asyncio
async def test_router_waits_four_minutes_before_sending_safe_fallback(monkeypatch):
    """Проверяет обязательную задержку перед публикацией safe fallback."""
    sleep = AsyncMock()
    monkeypatch.setattr(reply_router, "asyncio", SimpleNamespace(sleep=sleep), raising=False)
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock()),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system+persona")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock()),
        swarm_user_ids={202, 303},
        security_settings_getter=lambda: SimpleNamespace(swarm_allow_external_llm_for_replies=False),
    )
    event = _build_event(sender_id=999)

    handled = await router.handle_event(event)

    assert handled is True
    sleep.assert_awaited_once_with(240)
    event.reply.assert_awaited_once_with(SAFE_REPLY_FALLBACK_TEXT)


@pytest.mark.asyncio
async def test_router_replaces_unsafe_model_output_with_fallback():
    """Проверяет защиту публикации небезопасного текста модели."""
    history = SimpleNamespace(
        get_session_history=AsyncMock(return_value=[]),
        save_message=AsyncMock(),
    )
    gemini_client = SimpleNamespace(
        generate_reply=AsyncMock(return_value="https://t.me/+secret"),
        is_output_safe=lambda text: False,
    )
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=history,
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system+persona")),
        gemini_client=gemini_client,
        swarm_user_ids={202, 303},
        manager=SimpleNamespace(human_slot=lambda _bot_id: _AsyncNullContext()),
    )

    event = _build_event(sender_id=999, raw_text="Как думаешь?")

    handled = await router.handle_event(event)

    assert handled is True
    event.reply.assert_awaited_once_with(SAFE_REPLY_FALLBACK_TEXT)


@pytest.mark.asyncio
async def test_router_rate_limits_same_sender_for_same_bot(monkeypatch):
    """Проверяет rate limit на повторные addressed reply."""
    history = SimpleNamespace(
        get_session_history=AsyncMock(return_value=[]),
        save_message=AsyncMock(),
    )
    gemini_client = SimpleNamespace(generate_reply=AsyncMock(return_value="Ответ Анны"))
    fake_time = {"value": 1000.0}
    monkeypatch.setattr("userbot.reply_router.time.monotonic", lambda: fake_time["value"])
    rate_limiter = _ReplyRateLimiter()
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=history,
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system+persona")),
        gemini_client=gemini_client,
        swarm_user_ids={202, 303},
        manager=SimpleNamespace(human_slot=lambda _bot_id: _AsyncNullContext()),
        security_settings_getter=lambda: SimpleNamespace(
            swarm_allow_external_llm_for_replies=True,
            swarm_addressed_reply_rate_limit_count=1,
            swarm_addressed_reply_rate_limit_window_seconds=60,
        ),
        rate_limiter=rate_limiter,
    )

    first_handled = await router.handle_event(_build_event(sender_id=999, raw_text="Первый"))
    second_event = _build_event(sender_id=999, raw_text="Второй")
    second_handled = await router.handle_event(second_event)

    assert first_handled is True
    assert second_handled is False
    gemini_client.generate_reply.assert_awaited_once()
    second_event.reply.assert_not_awaited()


class _AsyncNullContext:
    """Минимальный async context manager для тестов."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False
