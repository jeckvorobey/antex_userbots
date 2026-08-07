"""Управление постоянным пулом Telethon-клиентов для swarm-режима."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from core.runtime_models import BotRuntimeState, SwarmBotProfile
from userbot.client import AccountMessagingUnavailableError, UserBotClient


logger = logging.getLogger(__name__)


class _BotGate:
    """Координатор human/scheduled задач для одного бота."""

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._owner: str | None = None
        self._human_waiters = 0

    @asynccontextmanager
    async def human_slot(self) -> AsyncIterator[None]:
        """Даёт приоритет human reply над scheduled задачами."""
        async with self._condition:
            self._human_waiters += 1
            while self._owner is not None:
                await self._condition.wait()
            self._human_waiters -= 1
            self._owner = "human"
        try:
            yield
        finally:
            async with self._condition:
                self._owner = None
                self._condition.notify_all()

    @asynccontextmanager
    async def scheduled_slot(self) -> AsyncIterator[bool]:
        """Пытается занять слот для scheduled задачи без ожидания."""
        async with self._condition:
            if self._owner is not None or self._human_waiters > 0:
                yield False
                return
            self._owner = "scheduled"
        try:
            yield True
        finally:
            async with self._condition:
                self._owner = None
                self._condition.notify_all()


class SwarmManager:
    """Запускает, координирует и супервизит активный пул userbot-клиентов."""

    def __init__(
        self,
        *,
        bot_profiles: list[SwarmBotProfile],
        client_factory: Callable[[SwarmBotProfile], UserBotClient | Any],
        startup_hook: Callable[[SwarmBotProfile, UserBotClient | Any], Any] | None = None,
        startup_quarantine_bot: Callable[[str, str], Any] | None = None,
        reconnect_backoff_seconds: tuple[float, ...] = (1.0, 3.0, 10.0, 30.0),
    ) -> None:
        self.bot_profiles = bot_profiles
        self.client_factory = client_factory
        self.startup_hook = startup_hook
        self.startup_quarantine_bot = startup_quarantine_bot
        self.reconnect_backoff_seconds = reconnect_backoff_seconds
        self.clients: dict[str, UserBotClient | Any] = {}
        self.runtime_states: dict[str, BotRuntimeState] = {
            profile.id: BotRuntimeState(bot_id=profile.id) for profile in bot_profiles if profile.enabled
        }
        self.swarm_user_ids: set[int] = set()
        self.active_bot_ids: list[str] = []
        self.disabled_bot_ids: set[str] = set()
        self._gates: dict[str, _BotGate] = {}
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Запускает всех enabled-ботов и собирает их Telegram user_id."""
        for profile in self.bot_profiles:
            if not profile.enabled:
                logger.info("swarm: bot_id=%s отключён конфигурацией", profile.id)
                continue
            try:
                await self._start_single_bot(profile)
            except AccountMessagingUnavailableError as exc:
                if self.startup_quarantine_bot is not None:
                    try:
                        result = self.startup_quarantine_bot(profile.id, str(exc))
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        logger.exception("swarm: не удалось сохранить startup quarantine для bot_id=%s", profile.id)
                await self.disable_bot(profile.id, reason=str(exc))
                logger.error(
                    "swarm: bot_id=%s заморожен или глобально недоступен для messaging; "
                    "требует внимания, auto_reuse=false reason=%s",
                    profile.id,
                    exc,
                )
            except Exception as exc:
                state = self.runtime_states[profile.id]
                state.mark_failed(str(exc))
                logger.exception("swarm: bot_id=%s исключён из активного пула при startup: %s", profile.id, exc)

    async def stop(self) -> None:
        """Останавливает все активные клиенты и завершает supervise loops."""
        self._stop_event.set()
        for bot_id, client in self.clients.items():
            logger.info("swarm: остановка клиента bot_id=%s", bot_id)
            await client.stop()
        for state in self.runtime_states.values():
            state.mark_stopped()

    async def supervise_bot(self, bot_id: str) -> None:
        """Поддерживает bot online и переподключает его после падений."""
        profile = self.get_profile(bot_id)
        state = self.runtime_states[bot_id]

        while not self._stop_event.is_set() and bot_id not in self.disabled_bot_ids:
            client = self.get_client(bot_id)
            try:
                logger.info("swarm: bot_id=%s переходит в ожидание Telegram-событий", bot_id)
                await client.run_until_disconnected()
                if self._stop_event.is_set() or bot_id in self.disabled_bot_ids:
                    break
                logger.warning("swarm: bot_id=%s отключился без явной ошибки, будет переподключение", bot_id)
                await self._reconnect_bot(profile, state)
            except asyncio.CancelledError:
                logger.info("swarm: supervise loop остановлен для bot_id=%s", bot_id)
                raise
            except Exception as exc:
                if bot_id in self.disabled_bot_ids:
                    logger.info("swarm: bot_id=%s не будет переподключён после runtime disable", bot_id)
                    break
                logger.exception("swarm: ошибка клиента bot_id=%s: %s", bot_id, exc)
                await self._reconnect_bot(profile, state, exc)

    def get_client(self, bot_id: str) -> UserBotClient | Any:
        """Возвращает активный клиент по bot_id."""
        return self.clients[bot_id]

    def get_profile(self, bot_id: str) -> SwarmBotProfile:
        """Возвращает профиль бота."""
        for profile in self.bot_profiles:
            if profile.id == bot_id:
                return profile
        raise KeyError(bot_id)

    def is_active(self, bot_id: str) -> bool:
        """Проверяет, доступен ли аккаунт для новых отправок."""
        return bot_id in self.active_bot_ids and bot_id not in self.disabled_bot_ids

    async def disable_bot(self, bot_id: str, *, reason: str) -> None:
        """Немедленно выводит аккаунт из runtime-пула после постоянного Telegram запрета."""
        if bot_id in self.disabled_bot_ids:
            return
        self.disabled_bot_ids.add(bot_id)
        if bot_id in self.active_bot_ids:
            self.active_bot_ids.remove(bot_id)
        profile = self.get_profile(bot_id)
        profile.enabled = False
        self.runtime_states[bot_id].mark_disabled(reason)
        client = self.clients.get(bot_id)
        if client is not None:
            await client.stop()
        logger.error("swarm: bot_id=%s отключён runtime reason=%s", bot_id, reason)

    @asynccontextmanager
    async def human_slot(self, bot_id: str) -> AsyncIterator[None]:
        """Даёт приоритет human reply для конкретного бота."""
        logger.info("swarm: bot_id=%s ожидает human slot", bot_id)
        async with self._gates[bot_id].human_slot():
            logger.info("swarm: bot_id=%s занял human slot", bot_id)
            yield
            logger.info("swarm: bot_id=%s освободил human slot", bot_id)

    @asynccontextmanager
    async def scheduled_slot(self, bot_id: str) -> AsyncIterator[bool]:
        """Пытается занять scheduled slot без гонки с human reply."""
        gate = self._gates.get(bot_id)
        if not self.is_active(bot_id) or gate is None:
            logger.warning("swarm: bot_id=%s не получил scheduled slot, потому что недоступен", bot_id)
            yield False
            return
        async with gate.scheduled_slot() as acquired:
            if acquired:
                logger.info("swarm: bot_id=%s занял scheduled slot", bot_id)
            else:
                logger.info("swarm: bot_id=%s не получил scheduled slot из-за приоритета human/busy", bot_id)
            yield acquired
            if acquired:
                logger.info("swarm: bot_id=%s освободил scheduled slot", bot_id)

    async def _start_single_bot(self, profile: SwarmBotProfile) -> None:
        """Запускает одного бота и регистрирует его runtime-state."""
        client = self.client_factory(profile)
        await client.start()
        # Клиент регистрируется до startup-hook, чтобы quarantine мог корректно остановить его.
        self.clients[profile.id] = client
        if self.startup_hook is not None:
            result = self.startup_hook(profile, client)
            if asyncio.iscoroutine(result):
                await result
        current_user = await client.get_current_user()
        telegram_user_id = getattr(current_user, "id", None)

        self.clients[profile.id] = client
        if profile.id not in self.active_bot_ids:
            self.active_bot_ids.append(profile.id)
        self._gates.setdefault(profile.id, _BotGate())

        profile.telegram_user_id = telegram_user_id
        state = self.runtime_states[profile.id]
        state.mark_started()
        if isinstance(telegram_user_id, int):
            self.swarm_user_ids.add(telegram_user_id)
        logger.info("swarm: bot_id=%s успешно запущен me.id=%s", profile.id, telegram_user_id)

    async def _reconnect_bot(self, profile: SwarmBotProfile, state: BotRuntimeState, exc: Exception | None = None) -> None:
        """Перезапускает клиента с backoff."""
        error_text = str(exc) if exc is not None else "disconnected"
        state.mark_error(error_text)
        profile.reconnect_attempts = state.reconnect_attempts
        delay = self._pick_reconnect_delay(state.reconnect_attempts)
        logger.warning(
            "swarm: bot_id=%s reconnect attempt=%s delay=%.1f error=%s",
            profile.id,
            state.reconnect_attempts,
            delay,
            error_text,
        )
        await asyncio.sleep(delay)
        if self._stop_event.is_set():
            return
        await self.clients[profile.id].stop()
        await self._start_single_bot(profile)

    def _pick_reconnect_delay(self, attempt: int) -> float:
        """Возвращает backoff delay для reconnect."""
        if attempt <= 0:
            return self.reconnect_backoff_seconds[0]
        index = min(attempt - 1, len(self.reconnect_backoff_seconds) - 1)
        return self.reconnect_backoff_seconds[index]
