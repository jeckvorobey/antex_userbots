"""Provider-neutral контракт генерации, redaction и output safety."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


TELEGRAM_INVITE_RE = re.compile(r"https?://t\.me/(?:\+|joinchat/)\S+", re.IGNORECASE)
CREDENTIAL_URL_RE = re.compile(
    r"[a-z][a-z0-9+.-]*://[^\s/@]+(?::[^\s/@]*)?@[^\s<>\[\]{}()]+",
    re.IGNORECASE,
)
HTTP_URL_RE = re.compile(r"https?://[^\s<>\[\]{}()]+", re.IGNORECASE)
URI_RE = re.compile(r"[a-z][a-z0-9+.-]*://[^\s<>\[\]{}()]+", re.IGNORECASE)
SCHEMELESS_DOMAIN_RE = re.compile(
    r"(?<![\w@])(?:www\.)?[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z]{2,})(?:/[^\s<>\[\]{}()]*)?",
    re.IGNORECASE,
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_ -]?key|token|secret|session[_ -]?string|api[_ -]?hash)\b\s*[:=]\s*\S+"
)
LONG_SECRET_RE = re.compile(r"\b(?=[A-Za-z0-9_\-]{32,}\b)(?=.*[A-Za-z])(?=.*\d)[A-Za-z0-9_\-]+\b")
MENTION_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{3,}")
ALLOWED_OUTPUT_URLS = frozenset({"https://t.me/tt_exchenge_bot/antex"})
URL_TRAILING_PUNCTUATION = ".,!?;:'\""


class GenerationError(RuntimeError):
    """Базовая безопасная ошибка внешней генерации текста."""


class TemporaryGenerationError(GenerationError):
    """Временная ошибка провайдера после исчерпания SDK retries."""


class TextGenerationClient(ABC):
    """Общий async-интерфейс генерации и единые правила безопасности."""

    def __init__(self, max_output_chars: int = 400, max_mentions_per_message: int = 2) -> None:
        self.max_output_chars = max(1, max_output_chars)
        self.max_mentions_per_message = max(0, max_mentions_per_message)

    @abstractmethod
    async def generate_reply(
        self,
        system_prompt: str,
        history: list[dict[str, Any]],
        user_message: str,
    ) -> str:
        """Генерирует ответ с учётом истории."""

    @abstractmethod
    async def start_topic(self, system_prompt: str, topic: str) -> str:
        """Генерирует стартовое сообщение по теме."""

    @abstractmethod
    async def close(self) -> None:
        """Закрывает принадлежащие клиенту сетевые ресурсы."""

    def sanitize_for_prompt(self, text: str) -> str:
        """Редактирует очевидно чувствительный текст перед внешним запросом."""
        sanitized = CREDENTIAL_URL_RE.sub("<redacted_credential_url>", text)
        sanitized = TELEGRAM_INVITE_RE.sub("<redacted_telegram_invite>", sanitized)
        sanitized = SECRET_ASSIGNMENT_RE.sub(r"\1=<redacted_secret>", sanitized)
        return LONG_SECRET_RE.sub("<redacted_secret>", sanitized)

    def sanitize_history_for_prompt(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Возвращает копию истории с очищенными текстовыми полями."""
        sanitized_history: list[dict[str, Any]] = []
        for item in history:
            sanitized_item = dict(item)
            text = sanitized_item.get("text")
            if isinstance(text, str):
                sanitized_item["text"] = self.sanitize_for_prompt(text)
            sanitized_history.append(sanitized_item)
        return sanitized_history

    @staticmethod
    def render_history(history: list[dict[str, Any]]) -> str:
        """Преобразует историю диалога в прежний текстовый формат."""
        if not history:
            return ""
        rendered = [f"{item.get('role', 'user')}: {item.get('text', '')}" for item in history]
        return "История диалога:\n" + "\n".join(rendered)

    def is_output_safe(self, text: str) -> bool:
        """Проверяет пригодность модельного текста для Telegram."""
        normalized = text.strip()
        if not normalized or len(normalized) > self.max_output_chars:
            return False
        if TELEGRAM_INVITE_RE.search(normalized):
            return False
        if SECRET_ASSIGNMENT_RE.search(normalized) or LONG_SECRET_RE.search(normalized):
            return False
        without_allowed_urls = normalized
        for allowed_url in ALLOWED_OUTPUT_URLS:
            without_allowed_urls = without_allowed_urls.replace(allowed_url, "")
        if URI_RE.search(without_allowed_urls) or SCHEMELESS_DOMAIN_RE.search(without_allowed_urls):
            return False
        for match in HTTP_URL_RE.finditer(normalized):
            url = match.group(0).rstrip(URL_TRAILING_PUNCTUATION)
            if url not in ALLOWED_OUTPUT_URLS:
                return False
        return len(MENTION_RE.findall(normalized)) <= self.max_mentions_per_message
