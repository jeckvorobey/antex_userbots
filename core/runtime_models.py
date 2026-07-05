"""Runtime-модели для swarm-архитектуры."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class SwarmBotProfile:
    """Профиль одного бота в swarm-режиме."""

    id: str
    session_string: str
    persona_file: str
    enabled: bool = True
    temperature: float = 0.9
    session_env: str | None = None
    telegram_user_id: int | None = None
    reconnect_attempts: int = 0


@dataclass(slots=True)
class BotRuntimeState:
    """Текущее runtime-состояние одного бота."""

    bot_id: str
    status: str = "created"
    last_started_at: datetime | None = None
    last_error_at: datetime | None = None
    last_error_text: str | None = None
    reconnect_attempts: int = 0

    def mark_started(self) -> None:
        """Фиксирует успешный запуск клиента."""
        self.status = "running"
        self.last_started_at = datetime.now(UTC)
        self.last_error_at = None
        self.last_error_text = None
        self.reconnect_attempts = 0

    def mark_error(self, error_text: str) -> None:
        """Фиксирует ошибку клиента."""
        self.status = "reconnecting"
        self.last_error_at = datetime.now(UTC)
        self.last_error_text = error_text
        self.reconnect_attempts += 1

    def mark_failed(self, error_text: str) -> None:
        """Фиксирует фатальную ошибку и исключение бота из активного пула."""
        self.status = "error"
        self.last_error_at = datetime.now(UTC)
        self.last_error_text = error_text

    def mark_stopped(self) -> None:
        """Фиксирует штатную остановку клиента."""
        self.status = "stopped"


@dataclass(slots=True)
class GroupRuntimeState:
    """Runtime-состояние одной Telegram-группы."""

    group_id: str
    city: str
    enabled: bool = True
    group_chat_id: int | None = None
    group_target: str | None = None
    resolved_target: object | None = None
    resolved_chat_id: int | None = None
    last_resolved_at: datetime | None = None

    def mark_resolved(self, *, target: object, chat_id: int | None = None) -> None:
        """Фиксирует успешный resolve группы."""
        self.resolved_target = target
        self.resolved_chat_id = chat_id if chat_id is not None else self.group_chat_id
        self.last_resolved_at = datetime.now(UTC)

    def mark_disabled(self) -> None:
        """Отключает runtime-обработку группы."""
        self.enabled = False


@dataclass(slots=True)
class ExchangeDecision:
    """Результат выбора exchange orchestrator-ом."""

    initiator: SwarmBotProfile
    responder: SwarmBotProfile
    topic: str
    topic_key: str
    recent_questions: list[str] = field(default_factory=list)
    exchange_kind: str = "regular"
    important_scenario: str | None = None
    important_answer_intent: str | None = None
