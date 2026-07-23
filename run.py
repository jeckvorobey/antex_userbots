"""Точка входа для запуска swarm userbot."""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from random import randint
from types import SimpleNamespace
from urllib.parse import urlparse

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ai.gemini import GeminiClient, PromptLoader
from ai.history import MessageHistory
from ai.prompt_composer import PromptComposer
from core.config import SettingsReloadWatcher, load_settings_or_exit
from core.logging import setup_logging
from core.runtime_models import SwarmBotProfile
from userbot.client import UserBotClient
from userbot.exchange_store import ExchangeStore
from userbot.orchestrator import SwarmOrchestrator
from userbot.reply_router import AddressedReplyRouter
from userbot.scheduler import TopicSelector
from userbot.swarm_manager import SwarmManager


logger = logging.getLogger(__name__)


STARTUP_MEMBERSHIP_DELAY_SECONDS = (30, 60)
GROUP_JOIN_INTERVAL_SECONDS = 20.0


def _pick_startup_membership_delay_seconds() -> float:
    """Выбирает секундовую задержку перед проверкой membership при startup."""
    start_seconds, end_seconds = STARTUP_MEMBERSHIP_DELAY_SECONDS
    return float(randint(start_seconds, end_seconds))


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
        for resource in (self.history, self.exchange_store):
            close = getattr(resource, "close", None)
            if callable(close):
                result = close()
                if inspect.isawaitable(result):
                    await result


def _utc_now() -> datetime:
    """Возвращает текущее время в UTC."""
    return datetime.now(UTC)


def _iter_candidate_chat_ids(chat_id: int) -> tuple[int, ...]:
    """Возвращает упорядоченные peer ID для сопоставления Telegram-группы."""
    absolute_chat_id = abs(chat_id)

    if chat_id > 0:
        return chat_id, -chat_id, -(10**12 + chat_id)
    if absolute_chat_id >= 10**12:
        return chat_id, absolute_chat_id - 10**12, absolute_chat_id
    return chat_id, absolute_chat_id


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


@dataclass(slots=True)
class _GroupDialogIndex:
    """Индекс доступных клиенту Telegram-групп по id и public username."""

    by_chat_id: dict[int, object]
    by_username: dict[str, object]


def _add_group_to_dialog_index(
    dialog_index: _GroupDialogIndex,
    resolved_target: object,
    *,
    group_chat_id: int | None = None,
    group_target: str | None = None,
) -> object:
    """Добавляет dialog/entity в индекс и возвращает используемую entity."""
    wrapped_entity = getattr(resolved_target, "entity", None)
    entity = wrapped_entity or resolved_target
    if wrapped_entity is not None:
        is_group = getattr(resolved_target, "is_group", None)
        is_channel = getattr(resolved_target, "is_channel", None)
        if is_group is False and is_channel is False:
            return entity

    candidate_ids = [group_chat_id, getattr(resolved_target, "id", None)]
    if wrapped_entity is None:
        candidate_ids.append(getattr(entity, "id", None))
    for candidate_id in candidate_ids:
        if isinstance(candidate_id, int):
            dialog_index.by_chat_id[candidate_id] = entity

    configured_slug = _extract_public_target_slug(group_target)
    if configured_slug:
        dialog_index.by_username[configured_slug] = entity
    for candidate_username in (
        getattr(resolved_target, "username", None),
        getattr(entity, "username", None),
    ):
        if isinstance(candidate_username, str) and candidate_username.strip():
            dialog_index.by_username[candidate_username.strip().casefold()] = entity
    return entity


async def _build_group_dialog_index(telegram_client: object | None) -> _GroupDialogIndex:
    """Один раз индексирует все доступные Telegram-диалоги клиента."""
    dialog_index = _GroupDialogIndex(by_chat_id={}, by_username={})
    if telegram_client is None:
        return dialog_index

    iter_dialogs = getattr(telegram_client, "iter_dialogs", None)
    if iter_dialogs is None:
        return dialog_index

    async for dialog in iter_dialogs():
        _add_group_to_dialog_index(dialog_index, dialog)
    return dialog_index


def _find_group_in_dialog_index(
    dialog_index: _GroupDialogIndex,
    group_chat_id: int | None,
    group_target: str | None,
) -> object | None:
    """Ищет entity группы в предварительно построенном индексе."""
    if group_chat_id is not None:
        exact_target = dialog_index.by_chat_id.get(group_chat_id)
        if exact_target is not None:
            return exact_target
        for candidate_id in _iter_candidate_chat_ids(group_chat_id)[1:]:
            resolved_target = dialog_index.by_chat_id.get(candidate_id)
            if resolved_target is not None:
                return resolved_target

    expected_slug = _extract_public_target_slug(group_target)
    if expected_slug:
        return dialog_index.by_username.get(expected_slug)
    return None


async def _resolve_joined_group_dialog(
    telegram_client: object | None,
    group_chat_id: int | None,
    group_target: str | None = None,
    *,
    dialog_index: _GroupDialogIndex | None = None,
) -> object | None:
    """Возвращает dialog/entity только если клиент уже состоит в целевой группе."""
    if dialog_index is None:
        dialog_index = await _build_group_dialog_index(telegram_client)
    return _find_group_in_dialog_index(dialog_index, group_chat_id, group_target)


def _extract_join_result_target(join_result: object | None) -> object | None:
    """Извлекает entity группы из результата join-запроса Telethon."""
    if join_result is None:
        return None

    chats = getattr(join_result, "chats", None)
    if isinstance(chats, list):
        return chats[0] if chats else None
    if isinstance(join_result, (str, int)) or isinstance(getattr(join_result, "id", None), int):
        return join_result
    return None


def _extract_resolved_chat_id(resolved_target: object | None, fallback_chat_id: int | None) -> int | None:
    """Извлекает реальный chat_id группы из resolved entity или fallback."""
    if fallback_chat_id is not None:
        return fallback_chat_id
    target_id = getattr(resolved_target, "id", None)
    return target_id if isinstance(target_id, int) else None


def _group_target_cache_key(group_chat_id: int | None, group_target: str | None) -> tuple[int | None, str | None]:
    """Строит стабильный ключ кэша для настроенной Telegram-группы."""
    normalized_target = group_target.strip() if isinstance(group_target, str) else None
    public_slug = _extract_public_target_slug(normalized_target)
    if public_slug:
        normalized_target = f"@{public_slug}"
    return group_chat_id, normalized_target


def _get_resolved_group_target_cache(telegram_client: object) -> dict[tuple[int | None, str | None], object]:
    """Возвращает раздельный по группам кэш resolved entity клиента."""
    resolved_targets = getattr(telegram_client, "_resolved_group_targets", None)
    if isinstance(resolved_targets, dict):
        return resolved_targets
    resolved_targets = {}
    setattr(telegram_client, "_resolved_group_targets", resolved_targets)
    return resolved_targets


def _cache_resolved_group_target(
    telegram_client: object | None,
    group_chat_id: int | None,
    group_target: str | None,
    resolved_target: object,
) -> None:
    """Сохраняет entity независимо от кэшированных entity других групп."""
    if telegram_client is None:
        return
    cache = _get_resolved_group_target_cache(telegram_client)
    cache[_group_target_cache_key(group_chat_id, group_target)] = resolved_target


async def _resolve_group_target(
    telegram_client: object | None,
    group_chat_id: int | None,
    group_target: str | None = None,
) -> object | None:
    """Находит и кэширует entity целевой группы для вызовов Telethon."""
    if telegram_client is None:
        return None

    normalized_group_target = group_target.strip() if isinstance(group_target, str) else None
    cache_key = _group_target_cache_key(group_chat_id, group_target)
    resolved_targets = _get_resolved_group_target_cache(telegram_client)
    cached_target = resolved_targets.get(cache_key)
    if cached_target is not None:
        return cached_target

    joined_group_target = await _resolve_joined_group_dialog(telegram_client, group_chat_id, group_target)
    if joined_group_target is not None:
        _cache_resolved_group_target(telegram_client, group_chat_id, group_target, joined_group_target)
        return joined_group_target

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
        _cache_resolved_group_target(telegram_client, group_chat_id, group_target, resolved_target)
        return resolved_target

    logger.warning("Не удалось найти entity целевой группы: GROUP_CHAT_ID=%s GROUP_TARGET=%s", group_chat_id, group_target)
    return None


async def _ensure_group_membership(
    client_wrapper: UserBotClient,
    group_chat_id: int | None,
    group_target: str | None,
    bot_id: str,
    *,
    dialog_index: _GroupDialogIndex | None = None,
) -> object | None:
    """Гарантирует доступ клиента к целевой группе, при необходимости выполняя вступление."""
    telegram_client = client_wrapper.client
    resolved_target = await _resolve_joined_group_dialog(
        telegram_client,
        group_chat_id,
        group_target,
        dialog_index=dialog_index,
    )
    if resolved_target is not None:
        _cache_resolved_group_target(telegram_client, group_chat_id, group_target, resolved_target)
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

    resolved_target = _extract_join_result_target(join_result)
    if resolved_target is None:
        resolved_target = await _resolve_joined_group_dialog(telegram_client, group_chat_id, group_target)
    if resolved_target is None:
        resolved_target = await _resolve_group_target(telegram_client, group_chat_id, group_target)
    if resolved_target is not None:
        _cache_resolved_group_target(telegram_client, group_chat_id, group_target, resolved_target)
        if dialog_index is not None:
            _add_group_to_dialog_index(
                dialog_index,
                resolved_target,
                group_chat_id=group_chat_id,
                group_target=group_target,
            )
        logger.info("swarm: bot_id=%s успешно получил доступ к целевой группе после автovступления", bot_id)
        return resolved_target

    logger.warning("swarm: bot_id=%s не смог получить доступ к группе после автovступления", bot_id)
    return None


def _build_group_membership_startup_hook(
    *,
    group_chat_id: int | None,
    group_target: str | None,
):
    """Строит startup hook с случайной задержкой перед membership check."""

    async def startup_hook(profile: SwarmBotProfile, client_wrapper: UserBotClient) -> object | None:
        delay_seconds = _pick_startup_membership_delay_seconds()
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
):
    """Строит startup hook, который проверяет membership для всех enabled groups."""

    async def startup_hook(profile: SwarmBotProfile, client_wrapper: UserBotClient) -> dict[str, object | None]:
        delay_seconds = _pick_startup_membership_delay_seconds()
        logger.info(
            "swarm: bot_id=%s ожидает случайную задержку перед multi-group membership check: %.1f sec",
            profile.id,
            delay_seconds,
        )
        await asyncio.sleep(delay_seconds)
        dialog_index = await _build_group_dialog_index(client_wrapper.client)
        resolved: dict[str, object | None] = {}
        processed_group = False
        for group in groups:
            if not getattr(group, "enabled", True):
                continue
            group_id = getattr(group, "id")
            if processed_group:
                logger.info(
                    "swarm: bot_id=%s ожидает интервал между вступлениями в группы: %.1f sec перед group_id=%s",
                    profile.id,
                    GROUP_JOIN_INTERVAL_SECONDS,
                    group_id,
                )
                await asyncio.sleep(GROUP_JOIN_INTERVAL_SECONDS)
            resolved[group_id] = await _ensure_group_membership(
                client_wrapper,
                getattr(group, "group_chat_id", None),
                getattr(group, "group_target", None),
                profile.id,
                dialog_index=dialog_index,
            )
            processed_group = True
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


async def _build_runtime_context(settings: object) -> RuntimeContext:
    """Создаёт общие runtime-зависимости swarm."""
    history = MessageHistory(settings.db_path)
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
    logger.info("SwarmOrchestrator зарегистрирован: tick_seconds=%s groups=%s", current_settings.swarm_tick_seconds, len(current_groups))

    supervise_tasks = [asyncio.create_task(manager.supervise_bot(bot_id)) for bot_id in manager.active_bot_ids]
    try:
        await asyncio.gather(*supervise_tasks)
    finally:
        for task in supervise_tasks:
            task.cancel()
        await asyncio.gather(*supervise_tasks, return_exceptions=True)
        await manager.stop()


async def main() -> None:
    """Инициализирует и запускает swarm userbot."""
    settings = load_settings_or_exit()
    setup_logging(settings.log_level)
    logger.info("Запуск swarm userbot")
    if settings.mode != "swarm":
        raise ValueError("Поддерживается только mode=swarm")

    runtime = await _build_runtime_context(settings)
    scheduler = AsyncIOScheduler()
    scheduler.start()
    logger.info("Планировщик запущен")
    try:
        await _run_swarm_mode(settings, runtime, scheduler)
    finally:
        shutdown = getattr(scheduler, "shutdown", None)
        if callable(shutdown):
            result = shutdown(wait=False)
            if inspect.isawaitable(result):
                await result
        await runtime.close()
        logger.info("Swarm userbot остановлен")


if __name__ == "__main__":
    asyncio.run(main())
