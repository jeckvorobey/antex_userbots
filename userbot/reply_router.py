"""Адресная маршрутизация reply-сообщений в swarm-режиме."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable
import logging
from typing import Any

from telethon.errors import ChannelPrivateError, ChatWriteForbiddenError, UserBannedInChannelError, UserNotParticipantError

from ai.generation import TextGenerationClient
from ai.history import MessageHistory
from ai.prompt_composer import PromptComposer
from core.runtime_models import SwarmBotProfile
from userbot.swarm_manager import SwarmManager


logger = logging.getLogger(__name__)
SAFE_REPLY_FALLBACK_TEXT = "Не могу безопасно ответить на это прямо сейчас."
ADDRESSED_REPLY_DELAY_SECONDS = 4 * 60
PERMANENT_TELEGRAM_SEND_ERRORS = (
    ChannelPrivateError,
    ChatWriteForbiddenError,
    UserBannedInChannelError,
    UserNotParticipantError,
)


class _ReplyRateLimiter:
    """Скользящее окно ограничений для addressed reply."""

    def __init__(self) -> None:
        self._events: dict[tuple[int | None, int | None, str], deque[float]] = {}
        self._last_cleanup_at = 0.0

    def allow(self, *, chat_id: int | None, sender_id: int | None, bot_id: str, limit: int, window_seconds: int) -> bool:
        """Возвращает, можно ли обработать очередной reply в текущем окне."""
        key = (chat_id, sender_id, bot_id)
        now = time.monotonic()
        threshold = now - window_seconds
        self._cleanup_expired(now=now, threshold=threshold, window_seconds=window_seconds)
        bucket = self._events.setdefault(key, deque())
        while bucket and bucket[0] < threshold:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    def _cleanup_expired(self, *, now: float, threshold: float, window_seconds: int) -> None:
        """Периодически удаляет истёкшие timestamps вместе с пустыми ключами."""
        if now - self._last_cleanup_at < window_seconds:
            return
        self._last_cleanup_at = now
        for key, bucket in list(self._events.items()):
            while bucket and bucket[0] < threshold:
                bucket.popleft()
            if not bucket:
                self._events.pop(key, None)


class AddressedReplyRouter:
    """Обрабатывает только reply к сообщениям конкретного бота."""

    def __init__(
        self,
        *,
        bot_profile: SwarmBotProfile,
        history: MessageHistory | Any,
        prompt_composer: PromptComposer | Any,
        ai_client: TextGenerationClient | Any,
        swarm_user_ids: set[int],
        enabled_group_chat_ids: set[int] | None = None,
        manager: SwarmManager | Any | None = None,
        quarantine_bot: Callable[..., Any] | None = None,
        security_settings_getter: Callable[[], Any] | None = None,
        rate_limiter: _ReplyRateLimiter | None = None,
        monotonic_provider: Callable[[], float] | None = None,
    ) -> None:
        self.bot_profile = bot_profile
        self.history = history
        self.prompt_composer = prompt_composer
        self.ai_client = ai_client
        self.swarm_user_ids = swarm_user_ids
        self.enabled_group_chat_ids = enabled_group_chat_ids if enabled_group_chat_ids is not None else set()
        self.manager = manager
        self.quarantine_bot = quarantine_bot
        self.security_settings_getter = security_settings_getter or (lambda: None)
        self.rate_limiter = rate_limiter or _ReplyRateLimiter()
        self.monotonic_provider = monotonic_provider or time.monotonic
        self._pending_replies = 0

    async def handle_event(self, event: Any) -> bool:
        """Обрабатывает входящее сообщение, если оно адресовано текущему боту."""
        is_active = getattr(self.manager, "is_active", None)
        if callable(is_active) and not is_active(self.bot_profile.id):
            logger.warning(
                "router: reject event for inactive bot_id=%s event_id=%s chat_id=%s",
                self.bot_profile.id,
                getattr(event, "id", None),
                getattr(event, "chat_id", None),
            )
            return False
        chat_id = getattr(event, "chat_id", None)
        if chat_id not in self.enabled_group_chat_ids:
            logger.debug("router: bot_id=%s ignore event outside enabled groups chat_id=%s", self.bot_profile.id, chat_id)
            return False

        sender_id = getattr(event, "sender_id", None)
        if sender_id in self.swarm_user_ids:
            logger.debug("router: bot_id=%s ignore sender from swarm sender_id=%s", self.bot_profile.id, sender_id)
            return False

        if not getattr(event, "is_reply", False):
            logger.debug("router: bot_id=%s ignore non-reply event_id=%s", self.bot_profile.id, getattr(event, "id", None))
            return False

        if await self._is_bot_sender(event):
            logger.debug("router: bot_id=%s ignore telegram-bot sender sender_id=%s", self.bot_profile.id, sender_id)
            return False

        reply_message = await event.get_reply_message()
        if reply_message is None:
            logger.debug("router: bot_id=%s ignore missing reply_message event_id=%s", self.bot_profile.id, getattr(event, "id", None))
            return False

        if getattr(reply_message, "sender_id", None) != self.bot_profile.telegram_user_id:
            logger.debug(
                "router: bot_id=%s ignore reply to another bot reply_sender_id=%s",
                self.bot_profile.id,
                getattr(reply_message, "sender_id", None),
            )
            return False

        logger.info(
            "router: bot_id=%s handling addressed reply event_id=%s sender_id=%s",
            self.bot_profile.id,
            getattr(event, "id", None),
            sender_id,
        )
        security_settings = self.security_settings_getter()
        max_pending = getattr(security_settings, "swarm_addressed_reply_max_pending_per_bot", 3)
        if self._pending_replies >= max_pending:
            logger.warning(
                "router: bot_id=%s rejected addressed reply because pending capacity is exhausted pending=%s limit=%s",
                self.bot_profile.id,
                self._pending_replies,
                max_pending,
            )
            return False
        if not self.rate_limiter.allow(
            chat_id=chat_id,
            sender_id=sender_id,
            bot_id=self.bot_profile.id,
            limit=getattr(security_settings, "swarm_addressed_reply_rate_limit_count", 3),
            window_seconds=getattr(security_settings, "swarm_addressed_reply_rate_limit_window_seconds", 60),
        ):
            logger.warning(
                "router: bot_id=%s throttled addressed reply sender_id=%s chat_id=%s",
                self.bot_profile.id,
                sender_id,
                chat_id,
            )
            return False

        reply_due_at = self.monotonic_provider() + ADDRESSED_REPLY_DELAY_SECONDS
        self._pending_replies += 1
        try:
            if self.manager is None:
                return await self._process_reply(
                    event=event,
                    reply_message=reply_message,
                    reply_due_at=reply_due_at,
                )

            async with self.manager.human_slot(self.bot_profile.id):
                return await self._process_reply(
                    event=event,
                    reply_message=reply_message,
                    reply_due_at=reply_due_at,
                )
        finally:
            self._pending_replies -= 1

    async def _process_reply(self, *, event: Any, reply_message: Any, reply_due_at: float) -> bool:
        """Обрабатывает уже подтверждённый addressed reply."""
        sender_id = getattr(event, "sender_id", None)
        chat_id = getattr(event, "chat_id", None)
        reply_to_message_id = getattr(reply_message, "id", None)
        user_text = getattr(event, "raw_text", "")
        history = await self.history.get_session_history(chat_id=chat_id, bot_id=self.bot_profile.id)
        system_prompt = await self.prompt_composer.compose(
            "reply",
            bot_id=self.bot_profile.id,
            persona_file=self.bot_profile.persona_file,
        )
        security_settings = self.security_settings_getter()
        if getattr(security_settings, "swarm_allow_external_llm_for_replies", True):
            response_text = await self.ai_client.generate_reply(
                system_prompt=system_prompt,
                history=history,
                user_message=user_text,
            )
            output_safe_checker = getattr(self.ai_client, "is_output_safe", lambda _text: True)
            if not output_safe_checker(response_text):
                logger.warning("router: bot_id=%s replaced unsafe AI reply", self.bot_profile.id)
                response_text = SAFE_REPLY_FALLBACK_TEXT
        else:
            logger.info("router: bot_id=%s uses local fallback because reply LLM is disabled", self.bot_profile.id)
            response_text = SAFE_REPLY_FALLBACK_TEXT

        await self.history.save_message(
            user_id=sender_id,
            role="user",
            text=user_text,
            chat_id=chat_id,
            bot_id=self.bot_profile.id,
            message_origin="human_reply",
            reply_to_message_id=reply_to_message_id,
        )
        logger.info(
            "router: bot_id=%s waiting %.3f seconds before human reply event_id=%s",
            self.bot_profile.id,
            max(0.0, reply_due_at - self.monotonic_provider()),
            getattr(event, "id", None),
        )
        remaining_delay = max(0.0, reply_due_at - self.monotonic_provider())
        if remaining_delay > 0:
            await asyncio.sleep(remaining_delay)
        try:
            await event.reply(response_text)
        except PERMANENT_TELEGRAM_SEND_ERRORS as exc:
            reason = f"telegram_human_reply_send_forbidden:{type(exc).__name__}"
            quarantine_error: Exception | None = None
            if self.quarantine_bot is not None:
                try:
                    await self.quarantine_bot(
                        group_key=str(chat_id),
                        bot_id=self.bot_profile.id,
                        reason=reason,
                    )
                except Exception as persist_exc:
                    quarantine_error = persist_exc
                    logger.exception(
                        "router: не удалось сохранить quarantine после permanent Telegram send error "
                        "bot_id=%s",
                        self.bot_profile.id,
                    )
            manager_disable = getattr(self.manager, "disable_bot", None)
            if callable(manager_disable):
                await manager_disable(self.bot_profile.id, reason=reason)
                logger.error(
                    "router: permanently disabled bot after Telegram send error bot_id=%s chat_id=%s reason=%s auto_reuse=false",
                    self.bot_profile.id,
                    chat_id,
                    reason,
                )
                if quarantine_error is not None:
                    raise quarantine_error
                return False
            if quarantine_error is not None:
                raise quarantine_error
            raise
        await self.history.save_message(
            user_id=sender_id,
            role="assistant",
            text=response_text,
            chat_id=chat_id,
            bot_id=self.bot_profile.id,
            message_origin="human_reply",
            reply_to_message_id=reply_to_message_id,
        )
        logger.info(
            "router: bot_id=%s sent human reply event_id=%s reply_to_message_id=%s",
            self.bot_profile.id,
            getattr(event, "id", None),
            reply_to_message_id,
        )
        return True

    async def _is_bot_sender(self, event: Any) -> bool:
        """Проверяет, что отправитель не является Telegram-ботом."""
        sender = getattr(event, "sender", None)
        if sender is None:
            get_sender = getattr(event, "get_sender", None)
            if callable(get_sender):
                sender = await get_sender()
        return bool(getattr(sender, "bot", False))
