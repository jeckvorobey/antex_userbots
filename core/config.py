"""Настройки приложения: секреты из .env, несекретная конфигурация из TOML."""

from __future__ import annotations

import logging
import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlparse

from dotenv import dotenv_values
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.logging import setup_logging


logger = logging.getLogger(__name__)


def _empty_str_to_none(v: object) -> object:
    """Преобразует пустую строку в None для необязательных полей."""
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


def _require_non_empty_str(v: object) -> object:
    """Отклоняет пустые строки для обязательных текстовых настроек."""
    if not isinstance(v, str):
        return v

    normalized = v.strip()
    if normalized == "":
        raise PydanticCustomError("empty_env_value", "Значение не должно быть пустым")
    return normalized


def _normalize_optional_str(v: object) -> object:
    """Обрезает пробелы и приводит пустую строку к None."""
    v = _empty_str_to_none(v)
    if isinstance(v, str):
        return v.strip()
    return v


def _required_secret(v: object) -> SecretStr:
    """Нормализует обязательный секрет и сохраняет его в маскирующем типе."""
    raw_value = v.get_secret_value() if isinstance(v, SecretStr) else v
    normalized = _require_non_empty_str(raw_value)
    if not isinstance(normalized, str):
        raise PydanticCustomError("invalid_secret_value", "Секрет должен быть строкой")
    return SecretStr(normalized)


def _optional_secret(v: object) -> SecretStr | None:
    """Нормализует необязательный секрет и сохраняет его в маскирующем типе."""
    raw_value = v.get_secret_value() if isinstance(v, SecretStr) else v
    normalized = _normalize_optional_str(raw_value)
    if normalized is None:
        return None
    if not isinstance(normalized, str):
        raise PydanticCustomError("invalid_secret_value", "Секрет должен быть строкой")
    if urlparse(normalized).scheme.lower() not in {"http", "https", "socks5", "socks5h"}:
        raise PydanticCustomError("invalid_proxy_scheme", "Unsupported proxy scheme")
    return SecretStr(normalized)


def _normalize_optional_chat_id(v: object) -> object:
    """Считает 0 и пустую строку отсутствующим chat_id."""
    v = _empty_str_to_none(v)
    if v == 0 or v == "0":
        return None
    return v


OptionalChatId = Annotated[int | None, BeforeValidator(_normalize_optional_chat_id)]
OptionalStr = Annotated[str | None, BeforeValidator(_normalize_optional_str)]
RequiredStr = Annotated[str, BeforeValidator(_require_non_empty_str)]
RequiredSecretStr = Annotated[SecretStr, BeforeValidator(_required_secret)]
OptionalSecretStr = Annotated[SecretStr | None, BeforeValidator(_optional_secret)]
MinuteRange = tuple[int, int]


class Secrets(BaseSettings):
    """Секретные настройки, которые остаются в .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openrouter_api_key: RequiredSecretStr
    proxy: OptionalSecretStr = None
    group_chat_id: OptionalChatId = None
    group_target: OptionalStr = None
    settings_path: OptionalStr = None


class _StrictModel(BaseModel):
    """Базовая модель TOML-секций с запретом неизвестных ключей."""

    model_config = ConfigDict(extra="forbid")


class TelegramConfig(_StrictModel):
    """Telegram API credentials из операторского TOML-файла."""

    api_id: int = Field(gt=0)
    api_hash: RequiredStr


class OpenRouterConfig(_StrictModel):
    """Несекретные параметры OpenRouter."""

    models: list[str]
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)

    @field_validator("models")
    @classmethod
    def validate_models(cls, value: list[str]) -> list[str]:
        """Требует основную и резервную уникальные модели в заданном порядке."""
        normalized = [model.strip() for model in value]
        if len(normalized) < 2:
            raise ValueError("openrouter.models должен содержать минимум две модели")
        if any(not model for model in normalized):
            raise ValueError("openrouter.models не должен содержать пустые модели")
        if len(set(normalized)) != len(normalized):
            raise ValueError("openrouter.models должен содержать уникальные модели")
        return normalized


class LoggingConfig(_StrictModel):
    """Параметры логирования."""

    level: str = "INFO"


class SwarmBotConfig(_StrictModel):
    """Конфигурация одного userbot в swarm-режиме."""

    id: str
    session_env: str
    persona_file: str
    enabled: bool = True
    temperature: float = Field(default=0.9, ge=0.0, le=2.0)

    @field_validator("persona_file")
    @classmethod
    def validate_persona_file(cls, value: str) -> str:
        """Запрещает выход persona_file за пределы bot_profiles_dir."""
        return _validate_relative_persona_file(value)


class SwarmBotRuntimeConfig(_StrictModel):
    """Развёрнутая runtime-конфигурация userbot с реальной строкой сессии."""

    id: str
    session_env: str
    session_string: str
    persona_file: str
    enabled: bool = True
    temperature: float = Field(default=0.9, ge=0.0, le=2.0)

    @field_validator("persona_file")
    @classmethod
    def validate_persona_file(cls, value: str) -> str:
        """Запрещает выход persona_file за пределы bot_profiles_dir."""
        return _validate_relative_persona_file(value)


class SwarmScheduleConfig(_StrictModel):
    """Расписание swarm-обменов."""

    active_windows_utc: list[str] = Field(default_factory=list)
    initiator_offset_minutes: MinuteRange = (0, 30)
    responder_delay_minutes: MinuteRange = (3, 10)
    max_turns_per_exchange: int = Field(default=2, ge=1)

    @field_validator("active_windows_utc")
    @classmethod
    def validate_active_windows_utc(cls, value: list[str]) -> list[str]:
        """Проверяет список UTC-окон в формате HH-HH."""
        validated: list[str] = []
        for item in value:
            normalized = _normalize_optional_str(item)
            if not isinstance(normalized, str):
                raise ValueError("Каждое окно active_windows_utc должно быть строкой")
            parts = normalized.split("-", maxsplit=1)
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                raise ValueError("active_windows_utc должен содержать окна в формате HH-HH")
            start_hour = int(parts[0])
            end_hour = int(parts[1])
            if not (0 <= start_hour <= 23 and 0 <= end_hour <= 24 and start_hour != end_hour):
                raise ValueError("active_windows_utc должен удовлетворять 0 <= start <= 23, 0 <= end <= 24 и start != end")
            validated.append(f"{start_hour}-{end_hour}")
        return validated

    @field_validator("initiator_offset_minutes", "responder_delay_minutes", mode="before")
    @classmethod
    def validate_minute_range(cls, value: object) -> object:
        """Проверяет диапазон минут [min, max]."""
        start, end = _read_pair(value, "Диапазон минут")
        if start < 0 or end < start:
            raise ValueError("Диапазон минут должен удовлетворять 0 <= min <= max")
        return (start, end)


class GroupScheduleOverride(_StrictModel):
    """Переопределения расписания для конкретной группы."""

    active_windows_utc: list[str] | None = None
    initiator_offset_minutes: MinuteRange | None = None
    responder_delay_minutes: MinuteRange | None = None
    max_turns_per_exchange: int | None = Field(default=None, ge=1)

    @field_validator("active_windows_utc")
    @classmethod
    def validate_active_windows_utc(cls, value: list[str] | None) -> list[str] | None:
        """Проверяет список UTC-окон, если он задан для группы."""
        if value is None:
            return None
        return SwarmScheduleConfig.validate_active_windows_utc(value)

    @field_validator("initiator_offset_minutes", "responder_delay_minutes", mode="before")
    @classmethod
    def validate_minute_range(cls, value: object) -> object:
        """Проверяет необязательный диапазон минут."""
        if value is None:
            return None
        return SwarmScheduleConfig.validate_minute_range(value)


class GroupConfig(_StrictModel):
    """Конфигурация одной Telegram-группы swarm."""

    id: RequiredStr
    city: RequiredStr
    enabled: bool = True
    group_chat_id: OptionalChatId = None
    group_target: OptionalStr = None
    schedule: GroupScheduleOverride = Field(default_factory=GroupScheduleOverride)

    @model_validator(mode="after")
    def validate_target(self) -> "GroupConfig":
        """Требует хотя бы один способ найти группу."""
        if self.group_chat_id is None and self.group_target is None:
            raise ValueError("group must define group_chat_id or group_target")
        return self


class GroupRuntimeConfig(_StrictModel):
    """Группа с вычисленным эффективным расписанием."""

    id: str
    city: str
    enabled: bool = True
    group_chat_id: int | None = None
    group_target: str | None = None
    active_windows_utc: list[str] = Field(default_factory=list)
    initiator_offset_minutes: MinuteRange = (0, 30)
    responder_delay_minutes: MinuteRange = (3, 10)
    max_turns_per_exchange: int = 2


class SwarmOrchestratorConfig(_StrictModel):
    """Параметры центрального orchestrator."""

    tick_seconds: int = Field(default=30, ge=1)
    silence_timeout_minutes: int = Field(default=60, ge=0)
    skip_if_recent_human_activity: bool = True


class SwarmSecurityConfig(_StrictModel):
    """Runtime security-настройки swarm."""

    allow_external_llm_for_replies: bool = True
    allow_external_llm_for_scheduled: bool = True
    addressed_reply_rate_limit_count: int = Field(default=3, ge=1)
    addressed_reply_rate_limit_window_seconds: int = Field(default=60, ge=1)
    addressed_reply_max_pending_per_bot: int = Field(default=3, ge=1)
    max_output_chars: int = Field(default=400, ge=1)
    max_mentions_per_message: int = Field(default=2, ge=0)
    history_retention_days: int = Field(default=30, ge=0)


class SwarmConfig(_StrictModel):
    """Секция swarm-настроек."""

    schedule: SwarmScheduleConfig = Field(default_factory=SwarmScheduleConfig)
    orchestrator: SwarmOrchestratorConfig = Field(default_factory=SwarmOrchestratorConfig)
    security: SwarmSecurityConfig = Field(default_factory=SwarmSecurityConfig)
    bots: list[SwarmBotConfig] = Field(default_factory=list)

    @field_validator("bots")
    @classmethod
    def validate_unique_bot_ids(cls, value: list[SwarmBotConfig]) -> list[SwarmBotConfig]:
        """Проверяет уникальность идентификаторов ботов."""
        seen: set[str] = set()
        for bot in value:
            normalized_bot_id = bot.id.strip().lower()
            if normalized_bot_id in seen:
                raise ValueError(f"duplicate swarm bot id: {bot.id}")
            seen.add(normalized_bot_id)
        return value


class AppConfig(_StrictModel):
    """Полная несекретная TOML-конфигурация."""

    groups: list[GroupConfig] = Field(default_factory=list)
    telegram: TelegramConfig
    openrouter: OpenRouterConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    swarm: SwarmConfig = Field(default_factory=SwarmConfig)

    @field_validator("groups")
    @classmethod
    def validate_unique_group_ids(cls, value: list[GroupConfig]) -> list[GroupConfig]:
        """Проверяет уникальность идентификаторов групп."""
        seen: set[str] = set()
        for group in value:
            normalized_group_id = group.id.strip().lower()
            if normalized_group_id in seen:
                raise ValueError(f"duplicate group id: {group.id}")
            seen.add(normalized_group_id)
        return value


def _read_pair(value: object, label: str) -> tuple[int, int]:
    """Читает пару целых значений из list/tuple для TOML-диапазонов."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{label} должен быть парой значений")
    first, second = value
    if not isinstance(first, int) or not isinstance(second, int):
        raise ValueError(f"{label} должен содержать целые числа")
    return first, second


def _validate_relative_persona_file(value: str) -> str:
    """Проверяет, что persona_file является относительным именем внутри директории профилей."""
    normalized = value.strip()
    if normalized == "":
        raise ValueError("persona_file не должен быть пустым")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("persona_file должен быть относительным путём внутри bot_profiles_dir")
    return normalized


_UNSET = object()
DEFAULT_SETTINGS_PATH = "config/settings.toml"
DEFAULT_MODE = "swarm"
DEFAULT_DB_PATH = "data/history.db"
DEFAULT_PROMPTS_DIR = "ai/prompts"
DEFAULT_TOPICS_PATH = "ai/prompts/topics.md"
DEFAULT_BOT_PROFILES_DIR = "ai/prompts/bots"
OPENROUTER_REQUEST_TIMEOUT_SECONDS = 45.0
OPENROUTER_RETRY_INITIAL_INTERVAL_MS = 500
OPENROUTER_RETRY_MAX_INTERVAL_MS = 5000
OPENROUTER_RETRY_MAX_ELAPSED_TIME_MS = 15000
OPENROUTER_RETRY_JITTER_MS = 300


def _load_toml_config(settings_path: str | Path | None, *, require_exists: bool = False) -> AppConfig:
    """Загружает TOML-конфигурацию или возвращает дефолты, если файл не задан."""
    if settings_path is None:
        return AppConfig()

    path = Path(settings_path)
    if not path.exists():
        if require_exists:
            raise FileNotFoundError(f"Файл настроек не найден: {path}")
        return AppConfig()

    with path.open("rb") as file_obj:
        data = tomllib.load(file_obj)
    return AppConfig.model_validate(data)


def _load_env_lookup(env_file: str | None | object) -> dict[str, str]:
    """Собирает карту переменных окружения с учётом .env и приоритета os.environ."""
    env_lookup: dict[str, str] = {}

    if isinstance(env_file, str):
        env_path = Path(env_file)
        if env_path.exists():
            env_lookup.update({key: value for key, value in dotenv_values(env_path).items() if value is not None})

    env_lookup.update(os.environ)
    return env_lookup


class Settings:
    """Фасад строгой runtime-конфигурации приложения."""

    def __init__(self, _env_file: str | None | object = ".env", **overrides: object) -> None:
        self._env_lookup = _load_env_lookup(_env_file)
        settings_path_override = overrides.pop("settings_path", _UNSET)
        secret_keys = {
            "openrouter_api_key",
            "proxy",
            "group_chat_id",
            "group_target",
        }
        required_secret_keys = {"openrouter_api_key"}
        secret_overrides = {key: overrides.pop(key) for key in list(overrides) if key in secret_keys}

        if required_secret_keys - secret_overrides.keys():
            secrets = Secrets(_env_file=_env_file)
            for key in secret_keys:
                setattr(self, key, secret_overrides.get(key, getattr(secrets, key)))
            if settings_path_override is _UNSET:
                settings_path = getattr(secrets, "settings_path", None) or DEFAULT_SETTINGS_PATH
                settings_path_required = "settings_path" in secrets.model_fields_set
            else:
                settings_path = settings_path_override
                settings_path_required = settings_path is not None
        else:
            for key in secret_keys:
                setattr(self, key, secret_overrides.get(key))
            if settings_path_override is _UNSET:
                settings_path = os.environ.get("SETTINGS_PATH") or DEFAULT_SETTINGS_PATH
                settings_path_required = "SETTINGS_PATH" in os.environ
            else:
                settings_path = settings_path_override
                settings_path_required = settings_path is not None

        self.openrouter_api_key = _required_secret(self.openrouter_api_key)
        self.proxy = _optional_secret(self.proxy)
        self._group_chat_id_fallback = self.group_chat_id
        self._group_target_fallback = self.group_target

        app_config = _load_toml_config(settings_path, require_exists=settings_path_required)
        self.settings_path = str(settings_path or DEFAULT_SETTINGS_PATH)
        self._settings_path_required = settings_path_required
        self._env_file = _env_file
        self._apply_app_config(app_config)

        for key, value in overrides.items():
            if not hasattr(self, key):
                raise ValueError(f"Неизвестная настройка: {key}")
            setattr(self, key, value)

    def _apply_app_config(self, config: AppConfig) -> None:
        """Пробрасывает секции TOML в публичные поля Settings."""
        self.mode = DEFAULT_MODE

        self.api_id = config.telegram.api_id
        self.api_hash = config.telegram.api_hash

        self.db_path = DEFAULT_DB_PATH
        self.topics_path = DEFAULT_TOPICS_PATH
        self.prompts_dir = DEFAULT_PROMPTS_DIR
        self.bot_profiles_dir = DEFAULT_BOT_PROFILES_DIR

        self.openrouter_models = list(config.openrouter.models)
        self.openrouter_temperature = config.openrouter.temperature
        self.openrouter_request_timeout_seconds = OPENROUTER_REQUEST_TIMEOUT_SECONDS
        self.openrouter_retry_initial_interval_ms = OPENROUTER_RETRY_INITIAL_INTERVAL_MS
        self.openrouter_retry_max_interval_ms = OPENROUTER_RETRY_MAX_INTERVAL_MS
        self.openrouter_retry_max_elapsed_time_ms = OPENROUTER_RETRY_MAX_ELAPSED_TIME_MS
        self.openrouter_retry_jitter_ms = OPENROUTER_RETRY_JITTER_MS

        self.log_level = config.logging.level

        self.swarm_schedule_active_windows_utc = list(config.swarm.schedule.active_windows_utc)
        self.swarm_initiator_offset_minutes = config.swarm.schedule.initiator_offset_minutes
        self.swarm_responder_delay_minutes = config.swarm.schedule.responder_delay_minutes
        self.swarm_max_turns_per_exchange = config.swarm.schedule.max_turns_per_exchange
        self.swarm_tick_seconds = config.swarm.orchestrator.tick_seconds
        self.swarm_silence_timeout_minutes = config.swarm.orchestrator.silence_timeout_minutes
        self.swarm_skip_if_recent_human_activity = config.swarm.orchestrator.skip_if_recent_human_activity
        self.swarm_allow_external_llm_for_replies = config.swarm.security.allow_external_llm_for_replies
        self.swarm_allow_external_llm_for_scheduled = config.swarm.security.allow_external_llm_for_scheduled
        self.swarm_addressed_reply_rate_limit_count = config.swarm.security.addressed_reply_rate_limit_count
        self.swarm_addressed_reply_rate_limit_window_seconds = (
            config.swarm.security.addressed_reply_rate_limit_window_seconds
        )
        self.swarm_addressed_reply_max_pending_per_bot = (
            config.swarm.security.addressed_reply_max_pending_per_bot
        )
        self.swarm_max_output_chars = config.swarm.security.max_output_chars
        self.swarm_max_mentions_per_message = config.swarm.security.max_mentions_per_message
        self.swarm_history_retention_days = config.swarm.security.history_retention_days
        self.swarm_bots = self._resolve_swarm_bots(config.swarm.bots)
        self.swarm_bot_ids = [bot.id for bot in self.swarm_bots]
        self.groups = self._resolve_groups(config.groups, config.swarm.schedule)
        self.enabled_groups = [group for group in self.groups if group.enabled]
        if self.groups:
            first_group = self.enabled_groups[0] if self.enabled_groups else self.groups[0]
            self.group_chat_id = self.group_chat_id if self.group_chat_id is not None else first_group.group_chat_id
            self.group_target = self.group_target if self.group_target is not None else first_group.group_target

    def _resolve_swarm_bots(self, bots: list[SwarmBotConfig]) -> list[SwarmBotRuntimeConfig]:
        """Разворачивает session_env каждого swarm-бота в фактическую строку сессии."""
        resolved_bots: list[SwarmBotRuntimeConfig] = []
        for bot in bots:
            session_string = self._env_lookup.get(bot.session_env)
            if session_string is None or session_string.strip() == "":
                raise ValueError(f"Swarm bot session env is missing or empty: {bot.session_env}")
            resolved_bots.append(
                SwarmBotRuntimeConfig.model_validate(
                    {
                        "id": bot.id,
                        "session_env": bot.session_env,
                        "session_string": session_string.strip(),
                        "persona_file": bot.persona_file,
                        "enabled": bot.enabled,
                        "temperature": bot.temperature,
                    },
                )
            )
        return resolved_bots

    def _resolve_groups(self, groups: list[GroupConfig], defaults: SwarmScheduleConfig) -> list[GroupRuntimeConfig]:
        """Вычисляет эффективные настройки групп с наследованием расписания."""
        source_groups = list(groups)
        if not source_groups and (self.group_chat_id is not None or self.group_target is not None):
            source_groups.append(
                GroupConfig(
                    id="legacy",
                    city="legacy",
                    enabled=True,
                    group_chat_id=self.group_chat_id,
                    group_target=self.group_target,
                )
            )

        resolved: list[GroupRuntimeConfig] = []
        for group in source_groups:
            schedule = group.schedule
            resolved.append(
                GroupRuntimeConfig(
                    id=group.id.strip(),
                    city=group.city.strip(),
                    enabled=group.enabled,
                    group_chat_id=group.group_chat_id,
                    group_target=group.group_target,
                    active_windows_utc=list(
                        defaults.active_windows_utc if schedule.active_windows_utc is None else schedule.active_windows_utc
                    ),
                    initiator_offset_minutes=(
                        defaults.initiator_offset_minutes
                        if schedule.initiator_offset_minutes is None
                        else schedule.initiator_offset_minutes
                    ),
                    responder_delay_minutes=(
                        defaults.responder_delay_minutes
                        if schedule.responder_delay_minutes is None
                        else schedule.responder_delay_minutes
                    ),
                    max_turns_per_exchange=(
                        defaults.max_turns_per_exchange
                        if schedule.max_turns_per_exchange is None
                        else schedule.max_turns_per_exchange
                    ),
                )
            )
        return resolved


class SettingsReloadWatcher:
    """Проверяет изменение TOML-файла и возвращает новый Settings без мутации старого."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._last_mtime = self._read_mtime(settings.settings_path)

    def poll(self) -> Settings | None:
        """Возвращает новые settings, если файл изменился."""
        current_mtime = self._read_mtime(self.settings.settings_path)
        if current_mtime == self._last_mtime:
            return None
        self._last_mtime = current_mtime
        reloaded = Settings(
            _env_file=self.settings._env_file,
            openrouter_api_key=self.settings.openrouter_api_key,
            proxy=self.settings.proxy,
            group_chat_id=self.settings._group_chat_id_fallback,
            group_target=self.settings._group_target_fallback,
            settings_path=self.settings.settings_path,
        )
        self.settings = reloaded
        return reloaded

    @staticmethod
    def _read_mtime(settings_path: str) -> int | None:
        """Читает mtime файла в наносекундах."""
        path = Path(settings_path)
        if not path.exists():
            return None
        return path.stat().st_mtime_ns


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Возвращает единственный экземпляр настроек приложения.

    Returns:
        Инициализированный объект Settings.
    """
    return Settings()


def load_settings_or_exit(default_log_level: str = "INFO") -> Settings:
    """Загружает настройки и завершает приложение при ошибке конфигурации."""
    try:
        return get_settings()
    except (ValidationError, OSError, tomllib.TOMLDecodeError, ValueError) as exc:
        setup_logging(default_log_level)
        logger.critical("Ошибка конфигурации: %s", exc)
        raise SystemExit(1) from exc
