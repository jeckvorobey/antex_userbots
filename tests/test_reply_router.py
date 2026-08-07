"""Тесты адресного reply-router для swarm-режима."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telethon.errors import UserBannedInChannelError

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
        enabled_group_chat_ids={-100555},
    )

    event = _build_event(sender_id=999, is_reply=False)

    handled = await router.handle_event(event)

    assert handled is False
    event.get_sender.assert_not_awaited()


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
async def test_router_rejects_every_event_when_enabled_group_allowlist_is_empty():
    """Проверяет fail-closed поведение до успешного resolve разрешённых групп."""
    history = SimpleNamespace(get_session_history=AsyncMock(), save_message=AsyncMock())
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=history,
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock()),
        swarm_user_ids={202, 303},
        enabled_group_chat_ids=set(),
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
        enabled_group_chat_ids={-100555},
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
        enabled_group_chat_ids={-100555},
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
        enabled_group_chat_ids={-100555},
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
        enabled_group_chat_ids={-100555},
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
async def test_router_persists_quarantine_after_permanent_send_error():
    """Permanent error в addressed reply запрещает повторное автоматическое использование аккаунта."""
    quarantine_bot = AsyncMock()
    manager = SimpleNamespace(
        is_active=lambda _bot_id: True,
        human_slot=lambda _bot_id: _AsyncNullContext(),
        disable_bot=AsyncMock(),
    )
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock()),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock(return_value="Ответ")),
        swarm_user_ids=set(),
        enabled_group_chat_ids={-100555},
        manager=manager,
        quarantine_bot=quarantine_bot,
    )
    event = _build_event(sender_id=999)
    event.reply.side_effect = UserBannedInChannelError(None)

    assert await router.handle_event(event) is False
    quarantine_bot.assert_awaited_once_with(
        group_key="-100555",
        bot_id="anna",
        reason="telegram_human_reply_send_forbidden:UserBannedInChannelError",
    )
    manager.disable_bot.assert_awaited_once_with(
        "anna", reason="telegram_human_reply_send_forbidden:UserBannedInChannelError"
    )


@pytest.mark.asyncio
async def test_router_disables_bot_when_quarantine_persistence_fails():
    """Ошибка SQLite не оставляет permanently forbidden аккаунт в active pool."""
    quarantine_bot = AsyncMock(side_effect=RuntimeError("sqlite unavailable"))
    manager = SimpleNamespace(
        is_active=lambda _bot_id: True,
        human_slot=lambda _bot_id: _AsyncNullContext(),
        disable_bot=AsyncMock(),
    )
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock()),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock(return_value="Ответ")),
        swarm_user_ids=set(),
        enabled_group_chat_ids={-100555},
        manager=manager,
        quarantine_bot=quarantine_bot,
    )
    event = _build_event(sender_id=999)
    event.reply.side_effect = UserBannedInChannelError(None)

    with pytest.raises(RuntimeError, match="sqlite unavailable"):
        await router.handle_event(event)

    manager.disable_bot.assert_awaited_once_with(
        "anna", reason="telegram_human_reply_send_forbidden:UserBannedInChannelError"
    )


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
        enabled_group_chat_ids={-100555},
        monotonic_provider=lambda: 1000.0,
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
        enabled_group_chat_ids={-100555},
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
        enabled_group_chat_ids={-100555},
        security_settings_getter=lambda: SimpleNamespace(swarm_allow_external_llm_for_replies=False),
        monotonic_provider=lambda: 1000.0,
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
        enabled_group_chat_ids={-100555},
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
        enabled_group_chat_ids={-100555},
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


def test_reply_rate_limiter_removes_expired_keys(monkeypatch):
    """Проверяет удаление неактивных sender buckets при периодической очистке."""
    fake_time = {"value": 1000.0}
    monkeypatch.setattr("userbot.reply_router.time.monotonic", lambda: fake_time["value"])
    limiter = _ReplyRateLimiter()

    assert limiter.allow(chat_id=1, sender_id=10, bot_id="anna", limit=1, window_seconds=60)
    assert (1, 10, "anna") in limiter._events

    fake_time["value"] = 1061.0
    assert limiter.allow(chat_id=1, sender_id=20, bot_id="anna", limit=1, window_seconds=60)

    assert (1, 10, "anna") not in limiter._events
    assert (1, 20, "anna") in limiter._events


@pytest.mark.asyncio
async def test_router_rejects_reply_when_pending_capacity_is_exhausted(monkeypatch):
    """Проверяет bounded pending очередь до history/Gemini второго reply."""
    sleep_started = asyncio.Event()
    release_sleep = asyncio.Event()

    async def controlled_sleep(_delay):
        sleep_started.set()
        await release_sleep.wait()

    monkeypatch.setattr(reply_router, "asyncio", SimpleNamespace(sleep=controlled_sleep), raising=False)
    history = SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock())
    gemini_client = SimpleNamespace(generate_reply=AsyncMock(return_value="Ответ"))
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=history,
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        gemini_client=gemini_client,
        swarm_user_ids=set(),
        enabled_group_chat_ids={-100555},
        security_settings_getter=lambda: SimpleNamespace(
            swarm_addressed_reply_rate_limit_count=3,
            swarm_addressed_reply_rate_limit_window_seconds=60,
            swarm_addressed_reply_max_pending_per_bot=1,
        ),
        monotonic_provider=lambda: 1000.0,
    )

    first_task = asyncio.create_task(router.handle_event(_build_event(sender_id=1)))
    await sleep_started.wait()
    second_event = _build_event(sender_id=2)

    assert await router.handle_event(second_event) is False
    second_event.reply.assert_not_awaited()
    assert gemini_client.generate_reply.await_count == 1

    release_sleep.set()
    assert await first_task is True


@pytest.mark.asyncio
async def test_router_releases_pending_capacity_after_failure():
    """Проверяет освобождение pending slot при ошибке обработки."""
    gemini_client = SimpleNamespace(
        generate_reply=AsyncMock(side_effect=[RuntimeError("failed"), "Ответ"]),
    )
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock()),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        gemini_client=gemini_client,
        swarm_user_ids=set(),
        enabled_group_chat_ids={-100555},
        security_settings_getter=lambda: SimpleNamespace(
            swarm_addressed_reply_rate_limit_count=3,
            swarm_addressed_reply_rate_limit_window_seconds=60,
            swarm_addressed_reply_max_pending_per_bot=1,
        ),
    )

    with pytest.raises(RuntimeError, match="failed"):
        await router.handle_event(_build_event(sender_id=1))

    assert await router.handle_event(_build_event(sender_id=2)) is True


@pytest.mark.asyncio
async def test_human_slot_wait_reduces_remaining_reply_deadline(monkeypatch):
    """Проверяет, что ожидание slot не запускает новый 240-секундный интервал."""
    sleep = AsyncMock()
    monkeypatch.setattr(reply_router, "asyncio", SimpleNamespace(sleep=sleep), raising=False)
    fake_time = {"value": 1000.0}

    class DelayedHumanSlot(_AsyncNullContext):
        async def __aenter__(self):
            fake_time["value"] = 1100.0

    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock()),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        gemini_client=SimpleNamespace(generate_reply=AsyncMock(return_value="Ответ")),
        swarm_user_ids=set(),
        enabled_group_chat_ids={-100555},
        manager=SimpleNamespace(human_slot=lambda _bot_id: DelayedHumanSlot()),
        monotonic_provider=lambda: fake_time["value"],
    )

    assert await router.handle_event(_build_event(sender_id=1)) is True

    sleep.assert_awaited_once_with(140.0)


class _AsyncNullContext:
    """Минимальный async context manager для тестов."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False
