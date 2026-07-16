"""Точка входа для запуска swarm userbot."""

from __future__ import annotations

import asyncio
import inspect
import logging
import signal
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import urlparse

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiosqlite

from ai.gemini import GeminiClient, PromptLoader
from ai.history import MessageHistory
from ai.prompt_composer import PromptComposer
from core.config import SettingsReloadWatcher, load_settings_or_exit
from core.logging import setup_logging
from core.runtime_lock import RuntimeInstanceLock
from core.runtime_models import SwarmBotProfile
from core.runtime_volume import RuntimeVolumeGuard
from userbot.client import UserBotClient
from userbot.exchange_store import ExchangeStore
from userbot.orchestrator import SwarmOrchestrator
from userbot.reply_router import AddressedReplyRouter
from userbot.scheduler import TopicSelector, pick_random_delay
from userbot.swarm_manager import SwarmManager


logger = logging.getLogger(__name__)


CONTAINER_HANDOVER_DELAY_SECONDS = 5.0
RUNTIME_LOCK_POLL_INTERVAL_SECONDS = 0.5
RUNTIME_LOCK_TIMEOUT_SECONDS = 60.0
SQLITE_BOOTSTRAP_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)
RUNTIME_RESOURCE_CLOSE_TIMEOUT_SECONDS = 3.0


async def _close_runtime_resource(resource: object) -> None:
    """Закрывает один runtime resource не дольше cleanup deadline."""
    close = getattr(resource, "close", None)
    if not callable(close):
        return
    result = close()
    if inspect.isawaitable(result):
        await asyncio.wait_for(result, timeout=RUNTIME_RESOURCE_CLOSE_TIMEOUT_SECONDS)


async def _close_runtime_resources(resources: list[object]) -> None:
    """Параллельно и best-effort закрывает runtime resources."""
    cleanup_results = await asyncio.gather(
        *(_close_runtime_resource(resource) for resource in resources),
        return_exceptions=True,
    )
    for resource, cleanup_result in zip(resources, cleanup_results, strict=True):
        if isinstance(cleanup_result, TimeoutError):
            logger.error(
                "Timeout закрытия runtime-ресурса type=%s timeout=%.1f sec",
                type(resource).__name__,
                RUNTIME_RESOURCE_CLOSE_TIMEOUT_SECONDS,
            )
        elif isinstance(cleanup_result, BaseException):
            logger.error(
                "Ошибка закрытия runtime-ресурса type=%s: %s",
                type(resource).__name__,
                cleanup_result,
            )


@dataclass(slots=True)
class RuntimeContext:
    """Переиспользуемые runtime-зависимости приложения."""

    history: MessageHistory
    prompt_loader: PromptLoader
    gemini_client: GeminiClient
    topic_selector: TopicSelector
    prompt_composer: PromptComposer
    exchange_store: ExchangeStore

    async def close(self) -> None:
        """Закрывает runtime-ресурсы с внешними соединениями."""
        await _close_runtime_resources([self.history, self.exchange_store])


def _utc_now() -> datetime:
    """Возвращает текущее время в UTC."""
    return datetime.now(UTC)


def _iter_candidate_chat_ids(chat_id: int) -> set[int]:
    """Возвращает набор идентификаторов для сопоставления чата и entity Telethon."""
    candidates = {chat_id, abs(chat_id)}
    absolute_chat_id = abs(chat_id)

    if chat_id > 0:
        candidates.add(-(10**12 + chat_id))
        return candidates
    if absolute_chat_id >= 10**12:
        candidates.add(absolute_chat_id - 10**12)
    return candidates


def _chat_id_matches(expected_chat_id: int, actual_chat_id: object) -> bool:
    """Проверяет, соответствует ли найденный идентификатор настроенному chat_id."""
    return isinstance(actual_chat_id, int) and actual_chat_id in _iter_candidate_chat_ids(expected_chat_id)


def _is_invite_link(target: str | None) -> bool:
    """Определяет, является ли target приватной invite-ссылкой Telegram."""
    if not isinstance(target, str):
        return False
    normalized = target.strip()
    return normalized.startswith(("https://t.me/+", "http://t.me/+", "https://t.me/joinchat/", "http://t.me/joinchat/"))


def _redact_group_target(target: object) -> object:
    """Скрывает приватные invite-ссылки Telegram в логах."""
    if isinstance(target, str) and _is_invite_link(target):
        return "<private invite link>"
    return target


def _normalize_public_group_target(target: str) -> str:
    """Нормализует публичный target группы до формы, совместимой с Telethon."""
    normalized = target.strip()
    parsed = urlparse(normalized)
    if parsed.scheme in {"http", "https"} and parsed.netloc == "t.me":
        path = parsed.path.strip("/")
        if path and "/" not in path:
            return f"@{path}" if not path.startswith("@") else path
    return normalized


def _extract_public_target_slug(target: str | None) -> str | None:
    """Извлекает username/slug публичной группы из target."""
    if not isinstance(target, str):
        return None

    normalized = _normalize_public_group_target(target)
    if normalized.startswith("@"):
        slug = normalized.removeprefix("@").strip()
        return slug.casefold() or None
    return None


def _dialog_matches_group(dialog: object, group_chat_id: int | None, group_target: str | None) -> bool:
    """Проверяет, относится ли dialog к целевой группе по id или публичному username."""
    dialog_id = getattr(dialog, "id", None)
    entity = getattr(dialog, "entity", None)
    entity_id = getattr(entity, "id", None)
    if group_chat_id is not None and (
        _chat_id_matches(group_chat_id, dialog_id) or _chat_id_matches(group_chat_id, entity_id)
    ):
        return True

    expected_slug = _extract_public_target_slug(group_target)
    if not expected_slug:
        return False

    for candidate in (getattr(dialog, "username", None), getattr(entity, "username", None)):
        if isinstance(candidate, str) and candidate.strip().casefold() == expected_slug:
            return True
    return False


async def _resolve_joined_group_dialog(
    telegram_client: object | None,
    group_chat_id: int | None,
    group_target: str | None = None,
) -> object | None:
    """Возвращает dialog/entity только если клиент уже состоит в целевой группе."""
    if telegram_client is None:
        return None

    iter_dialogs = getattr(telegram_client, "iter_dialogs", None)
    if iter_dialogs is None:
        return None

    async for dialog in iter_dialogs():
        if _dialog_matches_group(dialog, group_chat_id, group_target):
            entity = getattr(dialog, "entity", None)
            return entity or dialog
    return None


def _extract_join_result_target(join_result: object | None) -> object | None:
    """Извлекает entity группы из результата join-запроса Telethon."""
    if join_result is None:
        return None

    chats = getattr(join_result, "chats", None)
    if isinstance(chats, list) and chats:
        return chats[0]
    return join_result


def _extract_resolved_chat_id(resolved_target: object | None, fallback_chat_id: int | None) -> int | None:
    """Извлекает реальный chat_id группы из resolved entity или fallback."""
    if fallback_chat_id is not None:
        return fallback_chat_id
    target_id = getattr(resolved_target, "id", None)
    return target_id if isinstance(target_id, int) else None


async def _resolve_group_target(
    telegram_client: object | None,
    group_chat_id: int | None,
    group_target: str | None = None,
) -> object | None:
    """Находит и кэширует entity целевой группы для вызовов Telethon."""
    if telegram_client is None:
        return None

    cached_chat_id = getattr(telegram_client, "_resolved_group_chat_id", None)
    cached_group_target = getattr(telegram_client, "_resolved_group_target", None)
    cached_target = getattr(telegram_client, "_resolved_group_chat_target", None)
    if cached_chat_id == group_chat_id and cached_group_target == group_target and cached_target is not None:
        return cached_target

    joined_group_target = await _resolve_joined_group_dialog(telegram_client, group_chat_id, group_target)
    if joined_group_target is not None:
        setattr(telegram_client, "_resolved_group_chat_id", group_chat_id)
        setattr(telegram_client, "_resolved_group_target", group_target)
        setattr(telegram_client, "_resolved_group_chat_target", joined_group_target)
        return joined_group_target

    normalized_group_target = group_target.strip() if isinstance(group_target, str) else None
    if normalized_group_target:
        if _is_invite_link(normalized_group_target):
            logger.info("Пропуск get_entity для invite link target=%s", _redact_group_target(normalized_group_target))
            return None
        get_entity = getattr(telegram_client, "get_entity", None)
        if get_entity is None:
            logger.warning("Не удалось резолвить target группы '%s': get_entity недоступен", normalized_group_target)
            return None
        try:
            resolved_target = await get_entity(normalized_group_target)
        except ValueError:
            logger.warning("Не удалось резолвить target группы '%s' через get_entity", normalized_group_target)
            return None
        setattr(telegram_client, "_resolved_group_chat_id", group_chat_id)
        setattr(telegram_client, "_resolved_group_target", normalized_group_target)
        setattr(telegram_client, "_resolved_group_chat_target", resolved_target)
        return resolved_target

    logger.warning("Не удалось найти entity целевой группы: GROUP_CHAT_ID=%s GROUP_TARGET=%s", group_chat_id, group_target)
    return None


async def _ensure_group_membership(
    client_wrapper: UserBotClient,
    group_chat_id: int | None,
    group_target: str | None,
    bot_id: str,
) -> object | None:
    """Гарантирует доступ клиента к целевой группе, при необходимости выполняя вступление."""
    telegram_client = client_wrapper.client
    resolved_target = await _resolve_joined_group_dialog(telegram_client, group_chat_id, group_target)
    if resolved_target is not None:
        logger.info("swarm: bot_id=%s уже имеет доступ к целевой группе", bot_id)
        return resolved_target

    normalized_target = group_target.strip() if isinstance(group_target, str) else None
    if not normalized_target:
        logger.warning("swarm: bot_id=%s пропускает автovступление: group_target не задан", bot_id)
        return None

    if group_chat_id is not None and _is_invite_link(normalized_target):
        raise ValueError(
            f"bot_id={bot_id} не имеет доступа к группе с GROUP_CHAT_ID={group_chat_id}; "
            "обновите bot membership вручную или задайте актуальный публичный GROUP_TARGET"
        )

    if _is_invite_link(normalized_target):
        logger.info("swarm: bot_id=%s пытается вступить в группу по invite link", bot_id)
        join_result = await client_wrapper.join_invite_link(normalized_target)
    else:
        public_target = _normalize_public_group_target(normalized_target)
        logger.info("swarm: bot_id=%s пытается вступить в публичную группу: %s", bot_id, public_target)
        join_result = await client_wrapper.join_group(public_target)

    resolved_target = await _resolve_joined_group_dialog(telegram_client, group_chat_id, group_target)
    if resolved_target is None:
        resolved_target = _extract_join_result_target(join_result)
    if resolved_target is None:
        resolved_target = await _resolve_group_target(telegram_client, group_chat_id, group_target)
    if resolved_target is not None:
        logger.info("swarm: bot_id=%s успешно получил доступ к целевой группе после автovступления", bot_id)
        return resolved_target

    logger.warning("swarm: bot_id=%s не смог получить доступ к группе после автovступления", bot_id)
    return None


def _build_group_membership_startup_hook(
    *,
    group_chat_id: int | None,
    group_target: str | None,
    join_delay_minutes: tuple[int, int] = (1, 3),
):
    """Строит startup hook с случайной задержкой перед membership check."""

    async def startup_hook(profile: SwarmBotProfile, client_wrapper: UserBotClient) -> object | None:
        delay = pick_random_delay(join_delay_minutes)
        delay_seconds = delay.total_seconds()
        logger.info(
            "swarm: bot_id=%s ожидает случайную задержку перед membership check: %.1f sec",
            profile.id,
            delay_seconds,
        )
        await asyncio.sleep(delay_seconds)
        return await _ensure_group_membership(client_wrapper, group_chat_id, group_target, profile.id)

    return startup_hook


def _build_multi_group_membership_startup_hook(
    *,
    groups: list[object],
    join_delay_minutes: tuple[int, int] = (1, 3),
):
    """Строит startup hook, который проверяет membership для всех enabled groups."""

    async def startup_hook(profile: SwarmBotProfile, client_wrapper: UserBotClient) -> dict[str, object | None]:
        delay = pick_random_delay(join_delay_minutes)
        delay_seconds = delay.total_seconds()
        logger.info(
            "swarm: bot_id=%s ожидает случайную задержку перед multi-group membership check: %.1f sec",
            profile.id,
            delay_seconds,
        )
        await asyncio.sleep(delay_seconds)
        resolved: dict[str, object | None] = {}
        for group in groups:
            if not getattr(group, "enabled", True):
                continue
            group_id = getattr(group, "id")
            resolved[group_id] = await _ensure_group_membership(
                client_wrapper,
                getattr(group, "group_chat_id", None),
                getattr(group, "group_target", None),
                profile.id,
            )
        return resolved

    return startup_hook


async def _log_resolved_group(
    telegram_client: object | None,
    group_chat_id: int | None,
    group_target: str | None,
) -> None:
    """Логирует целевую группу, в которой будет работать swarm."""
    logger.info(
        "Целевая группа настроена: GROUP_CHAT_ID=%s GROUP_TARGET=%s",
        group_chat_id,
        _redact_group_target(group_target),
    )
    resolved_group_target = await _resolve_group_target(telegram_client, group_chat_id, group_target)
    if resolved_group_target is None:
        logger.warning(
            "Не удалось определить целевую группу при инициализации: GROUP_CHAT_ID=%s, GROUP_TARGET=%s",
            group_chat_id,
            _redact_group_target(group_target),
        )
        return

    logger.info(
        "Целевая группа определена: title=%s id=%s username=%s",
        getattr(resolved_group_target, "title", None) or "<без названия>",
        getattr(resolved_group_target, "id", None),
        getattr(resolved_group_target, "username", None),
    )


def _enabled_groups_from_settings(settings: object) -> list[object]:
    """Возвращает enabled groups или legacy group fallback."""
    groups = list(getattr(settings, "enabled_groups", []) or [])
    if groups:
        return groups
    group_chat_id = getattr(settings, "group_chat_id", None)
    group_target = getattr(settings, "group_target", None)
    if group_chat_id is None and group_target is None:
        return []
    return [
        SimpleNamespace(
            id="legacy",
            city="legacy",
            enabled=True,
            group_chat_id=group_chat_id,
            group_target=group_target,
            active_windows_utc=list(getattr(settings, "swarm_schedule_active_windows_utc", [])),
            initiator_offset_minutes=getattr(settings, "swarm_initiator_offset_minutes", (0, 30)),
            responder_delay_minutes=getattr(settings, "swarm_responder_delay_minutes", (3, 10)),
            max_turns_per_exchange=getattr(settings, "swarm_max_turns_per_exchange", 2),
        )
    ]


def _build_group_orchestrator_signature(
    *,
    group: object,
    group_target: object,
    group_chat_id: int | None,
    skip_if_recent_human_activity: bool,
) -> tuple[object, ...]:
    """Строит стабильную подпись group runtime-настроек для кеша orchestrator."""
    return (
        getattr(group, "id", None),
        getattr(group, "city", None),
        getattr(group, "group_chat_id", None),
        getattr(group, "group_target", None),
        group_chat_id,
        getattr(group_target, "id", None),
        getattr(group_target, "username", None),
        group_target if isinstance(group_target, (str, int)) else None,
        tuple(getattr(group, "active_windows_utc", []) or []),
        tuple(getattr(group, "initiator_offset_minutes", (0, 30))),
        tuple(getattr(group, "responder_delay_minutes", (3, 10))),
        getattr(group, "max_turns_per_exchange", 2),
        skip_if_recent_human_activity,
    )


def _get_cached_group_orchestrator(
    cache: dict[str, tuple[tuple[object, ...], object]],
    group_id: str,
    signature: tuple[object, ...],
    factory,
) -> object:
    """Возвращает кешированный orchestrator или пересоздаёт его при смене подписи."""
    cached = cache.get(group_id)
    if cached is not None and cached[0] == signature:
        return cached[1]

    orchestrator = factory()
    cache[group_id] = (signature, orchestrator)
    return orchestrator


def _prune_orchestrator_cache(
    cache: dict[str, tuple[tuple[object, ...], object]],
    active_group_ids: set[str],
) -> None:
    """Удаляет orchestrator-ы для отключённых или удалённых групп."""
    for group_id in list(cache):
        if group_id not in active_group_ids:
            cache.pop(group_id, None)


async def _build_runtime_context_once(settings: object) -> RuntimeContext:
    """Однократно создаёт общие runtime-зависимости swarm."""
    history = MessageHistory(settings.db_path)
    exchange_store: ExchangeStore | None = None
    try:
        await history.init_db()

        prompt_loader = PromptLoader(settings.prompts_dir)
        gemini_client = GeminiClient(
            settings.gemini_api_key,
            model_name=settings.gemini_model,
            proxy_url=settings.proxy_url,
            fallback_model_name=settings.gemini_fallback_model,
            max_retries=settings.gemini_max_retries,
            retry_backoff_seconds=settings.gemini_retry_backoff_seconds,
            retry_jitter_seconds=settings.gemini_retry_jitter_seconds,
            request_timeout_seconds=settings.gemini_request_timeout_seconds,
            temperature=settings.gemini_temperature,
            max_output_chars=getattr(settings, "swarm_max_output_chars", 400),
            max_mentions_per_message=getattr(settings, "swarm_max_mentions_per_message", 2),
        )
        topic_selector = TopicSelector(settings.topics_path)
        await topic_selector.load()
        prompt_composer = PromptComposer(prompt_loader=prompt_loader, bot_profiles_dir=settings.bot_profiles_dir)
        exchange_store = ExchangeStore(settings.db_path)
        await exchange_store.init_db()
        retention_days = getattr(settings, "swarm_history_retention_days", 30)
        await history.prune_older_than(retention_days=retention_days)
        await exchange_store.prune_older_than(retention_days=retention_days)

        logger.info(
            "RuntimeContext инициализирован: db_path=%s prompts_dir=%s topics=%s",
            settings.db_path,
            settings.prompts_dir,
            len(topic_selector.topics),
        )
        return RuntimeContext(
            history=history,
            prompt_loader=prompt_loader,
            gemini_client=gemini_client,
            topic_selector=topic_selector,
            prompt_composer=prompt_composer,
            exchange_store=exchange_store,
        )
    except BaseException:
        resources = [history]
        if exchange_store is not None:
            resources.append(exchange_store)
        await _close_runtime_resources(resources)
        raise


def _is_sqlite_lock_error(exc: aiosqlite.OperationalError) -> bool:
    """Определяет только временные SQLite lock errors, пригодные для retry."""
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


async def _build_runtime_context(settings: object) -> RuntimeContext:
    """Создаёт runtime-зависимости с ограниченным retry SQLite bootstrap."""
    for attempt in range(len(SQLITE_BOOTSTRAP_RETRY_DELAYS_SECONDS) + 1):
        try:
            return await _build_runtime_context_once(settings)
        except aiosqlite.OperationalError as exc:
            if not _is_sqlite_lock_error(exc) or attempt >= len(SQLITE_BOOTSTRAP_RETRY_DELAYS_SECONDS):
                raise
            delay = SQLITE_BOOTSTRAP_RETRY_DELAYS_SECONDS[attempt]
            logger.warning(
                "SQLite bootstrap временно заблокирован: attempt=%s/%s retry_in=%.1f sec error=%s",
                attempt + 1,
                len(SQLITE_BOOTSTRAP_RETRY_DELAYS_SECONDS) + 1,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    raise AssertionError("Недостижимая ветка SQLite bootstrap retry")


def _build_swarm_bot_profiles(settings: object) -> list[SwarmBotProfile]:
    """Преобразует конфигурацию в runtime-профили swarm-ботов."""
    profiles = [
        SwarmBotProfile(
            id=bot.id,
            session_string=bot.session_string,
            persona_file=bot.persona_file,
            enabled=bot.enabled,
            temperature=bot.temperature,
            session_env=bot.session_env,
        )
        for bot in settings.swarm_bots
        if bot.enabled
    ]
    logger.info("Подготовлены swarm-профили: enabled_bots=%s", len(profiles))
    return profiles


async def _register_swarm_handlers(
    manager: SwarmManager,
    runtime: RuntimeContext,
    settings_getter,
    enabled_group_chat_ids: set[int] | None = None,
) -> None:
    """Регистрирует addressed-reply handlers на всех клиентах swarm."""
    try:
        from telethon import events
    except ImportError:
        logger.warning("Регистрация swarm handler-ов пропущена: telethon не установлен")
        return

    active_profiles = {profile.id: profile for profile in manager.bot_profiles if profile.enabled}
    for bot_id in manager.active_bot_ids:
        profile = active_profiles.get(bot_id)
        if profile is None:
            logger.warning("Пропуск регистрации handler-а: активный bot_id=%s отсутствует в профилях", bot_id)
            continue
        client_wrapper = manager.get_client(profile.id)
        telegram_client = client_wrapper.client
        router = AddressedReplyRouter(
            bot_profile=profile,
            history=runtime.history,
            prompt_composer=runtime.prompt_composer,
            gemini_client=runtime.gemini_client,
            swarm_user_ids=manager.swarm_user_ids,
            enabled_group_chat_ids=enabled_group_chat_ids,
            manager=manager,
            security_settings_getter=settings_getter,
        )

        async def on_new_message(event: object, *, _router: AddressedReplyRouter = router) -> None:
            await _router.handle_event(event)

        telegram_client.add_event_handler(on_new_message, events.NewMessage())
        logger.info("Зарегистрирован addressed-reply handler: bot_id=%s", profile.id)


async def _run_swarm_mode(settings: object, runtime: RuntimeContext, scheduler: AsyncIOScheduler) -> None:
    """Запускает swarm-режим с постоянным пулом клиентов."""
    bot_profiles = _build_swarm_bot_profiles(settings)
    if len(bot_profiles) < 2:
        raise ValueError("Swarm mode requires at least two enabled bots")
    current_settings = settings
    current_groups = _enabled_groups_from_settings(current_settings)
    if not current_groups:
        raise ValueError("Swarm mode requires at least one enabled group")

    manager = SwarmManager(
        bot_profiles=bot_profiles,
        client_factory=lambda profile: UserBotClient(
            session_string=profile.session_string,
            api_id=settings.api_id,
            api_hash=settings.api_hash,
            proxy_url=settings.proxy_url,
        ),
        startup_hook=_build_multi_group_membership_startup_hook(
            groups=current_groups,
        ),
    )
    supervise_tasks: list[asyncio.Task[None]] = []
    try:
        await manager.start()
        if len(manager.active_bot_ids) < 2:
            raise ValueError("Swarm mode requires at least two active bots after startup")
        enabled_group_chat_ids = {
            group.group_chat_id for group in current_groups if isinstance(getattr(group, "group_chat_id", None), int)
        }
        await _register_swarm_handlers(manager, runtime, lambda: current_settings, enabled_group_chat_ids or None)

        first_client = manager.get_client(manager.active_bot_ids[0]).client
        for group in current_groups:
            await _log_resolved_group(first_client, group.group_chat_id, group.group_target)

        reload_watcher = SettingsReloadWatcher(current_settings)
        orchestrator_cache: dict[str, tuple[tuple[object, ...], object]] = {}

        async def orchestrator_tick() -> bool:
            nonlocal current_settings, current_groups
            reloaded_settings = reload_watcher.poll()
            if reloaded_settings is not None:
                current_settings = reloaded_settings
                current_groups = _enabled_groups_from_settings(current_settings)
                enabled_group_chat_ids.clear()
                enabled_group_chat_ids.update(
                    group.group_chat_id for group in current_groups if isinstance(getattr(group, "group_chat_id", None), int)
                )
                logger.info("settings reload: enabled_groups=%s", [group.id for group in current_groups])

            any_started = False
            _prune_orchestrator_cache(orchestrator_cache, {group.id for group in current_groups})
            for group in current_groups:
                resolved_group_target = await _resolve_group_target(
                    first_client,
                    getattr(group, "group_chat_id", None),
                    getattr(group, "group_target", None),
                )
                group_target = resolved_group_target or getattr(group, "group_target", None) or getattr(group, "group_chat_id", None)
                group_chat_id = _extract_resolved_chat_id(resolved_group_target, getattr(group, "group_chat_id", None))
                if group_target is None:
                    logger.warning("orchestrator: skip group without target group_id=%s", group.id)
                    continue
                signature = _build_group_orchestrator_signature(
                    group=group,
                    group_target=group_target,
                    group_chat_id=group_chat_id,
                    skip_if_recent_human_activity=current_settings.swarm_skip_if_recent_human_activity,
                )

                def build_orchestrator(
                    *,
                    _group=group,
                    _group_target=group_target,
                    _group_chat_id=group_chat_id,
                    _settings=current_settings,
                ) -> SwarmOrchestrator:
                    return SwarmOrchestrator(
                        bot_profiles=bot_profiles,
                        manager=manager,
                        topic_selector=runtime.topic_selector,
                        prompt_composer=runtime.prompt_composer,
                        gemini_client=runtime.gemini_client,
                        history=runtime.history,
                        exchange_store=runtime.exchange_store,
                        group_id=_group.id,
                        group_city=_group.city,
                        group_target=_group_target,
                        group_chat_id=_group_chat_id,
                        max_turns_per_exchange=_group.max_turns_per_exchange,
                        active_windows_utc=_group.active_windows_utc,
                        initiator_offset_minutes=_group.initiator_offset_minutes,
                        responder_delay_minutes=_group.responder_delay_minutes,
                        skip_if_recent_human_activity=_settings.swarm_skip_if_recent_human_activity,
                        allow_external_llm_for_scheduled=_settings.swarm_allow_external_llm_for_scheduled,
                        resolve_group_target=lambda telegram_client, _resolver_group=_group: _resolve_group_target(
                            telegram_client,
                            getattr(_resolver_group, "group_chat_id", None),
                            getattr(_resolver_group, "group_target", None),
                        ),
                    )

                orchestrator = _get_cached_group_orchestrator(
                    orchestrator_cache,
                    group.id,
                    signature,
                    build_orchestrator,
                )
                any_started = await orchestrator.run_once() or any_started
            return any_started

        scheduler.add_job(
            orchestrator_tick,
            "interval",
            seconds=current_settings.swarm_tick_seconds,
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "SwarmOrchestrator зарегистрирован: tick_seconds=%s groups=%s",
            current_settings.swarm_tick_seconds,
            len(current_groups),
        )

        supervise_tasks = [asyncio.create_task(manager.supervise_bot(bot_id)) for bot_id in manager.active_bot_ids]
        await asyncio.gather(*supervise_tasks)
    finally:
        for task in supervise_tasks:
            task.cancel()
        await asyncio.gather(*supervise_tasks, return_exceptions=True)
        await manager.stop()


def _handle_shutdown_signal(received_signal: signal.Signals, shutdown_event: asyncio.Event) -> None:
    """Переводит Unix signal в управляемый asyncio shutdown event."""
    if shutdown_event.is_set():
        return
    logger.info("Получен сигнал остановки: signal=%s", received_signal.name)
    shutdown_event.set()


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, shutdown_event: asyncio.Event) -> list[signal.Signals]:
    """Устанавливает обработчики container SIGTERM и интерактивного SIGINT."""
    installed: list[signal.Signals] = []
    for handled_signal in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(handled_signal, _handle_shutdown_signal, handled_signal, shutdown_event)
        except (NotImplementedError, RuntimeError):
            logger.warning("Async signal handler недоступен: signal=%s", handled_signal.name)
            continue
        installed.append(handled_signal)
    return installed


def _remove_signal_handlers(loop: asyncio.AbstractEventLoop, installed: list[signal.Signals]) -> None:
    """Удаляет только обработчики, установленные текущим lifecycle."""
    for handled_signal in installed:
        loop.remove_signal_handler(handled_signal)


async def _wait_for_shutdown(shutdown_event: asyncio.Event, timeout_seconds: float) -> bool:
    """Ожидает shutdown не дольше timeout и возвращает факт сигнала."""
    if shutdown_event.is_set():
        return True
    if timeout_seconds <= 0:
        return False
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=timeout_seconds)
    except TimeoutError:
        return False
    return True


async def _await_phase_or_shutdown(awaitable: object, shutdown_event: asyncio.Event) -> tuple[bool, object | None]:
    """Выполняет async startup-фазу и отменяет её при shutdown."""
    phase_task = asyncio.ensure_future(awaitable)
    shutdown_task = asyncio.create_task(shutdown_event.wait())
    done, _pending = await asyncio.wait((phase_task, shutdown_task), return_when=asyncio.FIRST_COMPLETED)
    if phase_task in done:
        shutdown_task.cancel()
        await asyncio.gather(shutdown_task, return_exceptions=True)
        return True, await phase_task

    phase_task.cancel()
    await asyncio.gather(phase_task, return_exceptions=True)
    return False, None


async def _shutdown_scheduler(scheduler: AsyncIOScheduler) -> None:
    """Останавливает scheduler и ожидает async-реализацию при её наличии."""
    shutdown = getattr(scheduler, "shutdown", None)
    if not callable(shutdown):
        return
    try:
        result = shutdown(wait=False)
        if inspect.isawaitable(result):
            await result
    except Exception as exc:
        logger.error("Ошибка остановки scheduler: %s", exc)


async def _run_application(settings: object, shutdown_event: asyncio.Event) -> None:
    """Управляет container handover и полным lifecycle runtime-ресурсов."""
    RuntimeVolumeGuard(settings.db_path).verify()
    runtime_lock = RuntimeInstanceLock(
        settings.db_path,
        poll_interval_seconds=RUNTIME_LOCK_POLL_INTERVAL_SECONDS,
        timeout_seconds=RUNTIME_LOCK_TIMEOUT_SECONDS,
    )
    runtime: RuntimeContext | None = None
    scheduler: AsyncIOScheduler | None = None
    scheduler_stopped = False
    swarm_task: asyncio.Task[None] | None = None

    try:
        logger.info("Ожидание container handover перед runtime startup: %.1f sec", CONTAINER_HANDOVER_DELAY_SECONDS)
        if await _wait_for_shutdown(shutdown_event, CONTAINER_HANDOVER_DELAY_SECONDS):
            logger.info("Startup отменён сигналом во время container handover")
            return
        if not await runtime_lock.acquire(shutdown_event=shutdown_event):
            logger.info("Startup отменён сигналом во время ожидания runtime lock")
            return

        initialized, runtime_result = await _await_phase_or_shutdown(_build_runtime_context(settings), shutdown_event)
        if not initialized:
            logger.info("Startup отменён сигналом во время SQLite bootstrap")
            return
        runtime = runtime_result
        if not isinstance(runtime, RuntimeContext) and not hasattr(runtime, "close"):
            raise TypeError("Runtime bootstrap вернул некорректный context")

        scheduler = AsyncIOScheduler()
        scheduler.start()
        logger.info("Планировщик запущен")

        swarm_task = asyncio.create_task(_run_swarm_mode(settings, runtime, scheduler))
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        done, _pending = await asyncio.wait((swarm_task, shutdown_task), return_when=asyncio.FIRST_COMPLETED)
        if swarm_task in done:
            shutdown_task.cancel()
            await asyncio.gather(shutdown_task, return_exceptions=True)
            await swarm_task
            return

        logger.info("Начало graceful shutdown swarm runtime")
        await _shutdown_scheduler(scheduler)
        scheduler_stopped = True
        swarm_task.cancel()
        await asyncio.gather(swarm_task, return_exceptions=True)
    finally:
        if swarm_task is not None and not swarm_task.done():
            swarm_task.cancel()
            await asyncio.gather(swarm_task, return_exceptions=True)
        if scheduler is not None and not scheduler_stopped:
            await _shutdown_scheduler(scheduler)
        if runtime is not None:
            await runtime.close()
        try:
            runtime_lock.release()
        except Exception as exc:
            logger.error("Ошибка освобождения runtime lock: %s", exc)
        logger.info("Swarm userbot остановлен")


async def main() -> None:
    """Инициализирует и запускает swarm userbot с graceful signal handling."""
    settings = load_settings_or_exit()
    setup_logging(settings.log_level)
    logger.info("Запуск swarm userbot")
    if settings.mode != "swarm":
        raise ValueError("Поддерживается только mode=swarm")

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()
    installed_signals = _install_signal_handlers(loop, shutdown_event)
    try:
        await _run_application(settings, shutdown_event)
    finally:
        _remove_signal_handlers(loop, installed_signals)


if __name__ == "__main__":
    asyncio.run(main())
