"""Асинхронный OpenRouter adapter для provider-neutral генерации."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from ai.generation import GenerationError, TemporaryGenerationError, TextGenerationClient


logger = logging.getLogger(__name__)
RETRY_STATUS_CODES = ["408", "429", "5XX", "524", "529"]
TEMPORARY_STATUS_CODES = {408, 429, 524, 529}
MAX_COMPLETION_TOKENS = 256


class OpenRouterClient(TextGenerationClient):
    """Вызывает OpenRouter Chat Completions с ZDR и ordered fallback."""

    def __init__(
        self,
        api_key: str,
        models: list[str],
        proxy: str | None = None,
        temperature: float | None = None,
        request_timeout_seconds: float = 45.0,
        retry_initial_interval_ms: int = 500,
        retry_max_interval_ms: int = 5000,
        retry_max_elapsed_time_ms: int = 15000,
        retry_jitter_ms: int = 300,
        max_output_chars: int = 400,
        max_mentions_per_message: int = 2,
    ) -> None:
        super().__init__(max_output_chars=max_output_chars, max_mentions_per_message=max_mentions_per_message)
        self.api_key = api_key
        self.models = list(models)
        self.proxy = proxy
        self.temperature = temperature
        self.request_timeout_seconds = request_timeout_seconds
        self.retry_initial_interval_ms = retry_initial_interval_ms
        self.retry_max_interval_ms = retry_max_interval_ms
        self.retry_max_elapsed_time_ms = retry_max_elapsed_time_ms
        self.retry_jitter_ms = retry_jitter_ms
        self._client: Any | None = None
        self._http_client: Any | None = None
        self._closed = False

    async def generate_reply(
        self,
        system_prompt: str,
        history: list[dict[str, Any]],
        user_message: str,
    ) -> str:
        """Генерирует ответ из очищенной истории и текущего сообщения."""
        prompt_parts = [
            self.render_history(self.sanitize_history_for_prompt(history)),
            f"Пользователь: {self.sanitize_for_prompt(user_message)}",
        ]
        user_context = "\n\n".join(part for part in prompt_parts if part)
        return await self._generate_text("reply", system_prompt, user_context)

    async def start_topic(self, system_prompt: str, topic: str) -> str:
        """Генерирует стартовое сообщение из очищенной темы."""
        user_context = f"Тема разговора: {self.sanitize_for_prompt(topic)}"
        return await self._generate_text("start_topic", system_prompt, user_context)

    async def close(self) -> None:
        """Идемпотентно закрывает SDK и принадлежащий adapter HTTPX client."""
        if self._closed:
            return
        self._closed = True
        client, http_client = self._client, self._http_client
        self._client = None
        self._http_client = None
        if client is not None:
            await client.__aexit__(None, None, None)
        if http_client is not None:
            await http_client.aclose()

    async def _generate_text(self, operation: str, system_prompt: str, user_context: str) -> str:
        """Отправляет один provider-routed запрос и нормализует первый ответ."""
        if self._closed:
            raise GenerationError("Клиент генерации уже закрыт")
        request: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_context},
            ],
            "models": self.models,
            "provider": {
                "zdr": True,
                "data_collection": "deny",
                "allow_fallbacks": True,
                "require_parameters": True,
            },
            "stream": False,
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        }
        if self.temperature is not None:
            request["temperature"] = self.temperature

        logger.info(
            "OpenRouter generation started: operation=%s models=%s proxy=%s",
            operation,
            len(self.models),
            self._describe_proxy(),
        )
        try:
            response = await self._get_client().chat.send_async(**request)
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise GenerationError("OpenRouter вернул пустой текст")
            return content.strip()
        except GenerationError:
            logger.warning("OpenRouter generation failed: operation=%s category=response", operation)
            raise
        except Exception as exc:
            status = self._extract_status_code(exc)
            category = "temporary" if self._is_temporary_error(exc, status) else "permanent"
            logger.warning(
                "OpenRouter generation failed: operation=%s category=%s status=%s",
                operation,
                category,
                status if status is not None else "unknown",
            )
            error_type = TemporaryGenerationError if category == "temporary" else GenerationError
            raise error_type("Ошибка генерации через OpenRouter") from None

    def _get_client(self) -> Any:
        """Лениво создаёт официальный SDK client с bounded retries."""
        if self._client is not None:
            return self._client
        sdk = _import_openrouter()
        retry_config = sdk.utils.RetryConfig(
            strategy="backoff",
            backoff=sdk.utils.BackoffStrategy(
                initial_interval=self.retry_initial_interval_ms,
                max_interval=self.retry_max_interval_ms,
                exponent=2.0,
                max_elapsed_time=self.retry_max_elapsed_time_ms,
                jitter_ms=self.retry_jitter_ms,
            ),
            retry_connection_errors=True,
            status_codes_override=RETRY_STATUS_CODES,
        )
        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "retry_config": retry_config,
            "timeout_ms": round(self.request_timeout_seconds * 1000),
        }
        if self.proxy:
            self._http_client = httpx.AsyncClient(proxy=self.proxy)
            kwargs["async_client"] = self._http_client
        self._client = sdk.OpenRouter(**kwargs)
        return self._client

    def _describe_proxy(self) -> str:
        """Возвращает proxy без учётных данных для логов."""
        if not self.proxy:
            return "off"
        parsed = urlparse(self.proxy)
        if parsed.scheme and parsed.hostname and parsed.port:
            return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
        return "configured"

    @staticmethod
    def _extract_status_code(exc: Exception) -> int | None:
        """Извлекает HTTP status без чтения потенциально чувствительного body."""
        status = getattr(exc, "status_code", None)
        if isinstance(status, int):
            return status
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        return status if isinstance(status, int) else None

    @staticmethod
    def _is_temporary_error(exc: Exception, status: int | None) -> bool:
        """Классифицирует только согласованные transport/status ошибки."""
        return (
            isinstance(exc, (httpx.NetworkError, httpx.TimeoutException, TimeoutError))
            or status in TEMPORARY_STATUS_CODES
            or (status is not None and 500 <= status <= 599)
        )


def _import_openrouter() -> Any:
    """Импортирует официальный SDK с понятной локальной ошибкой."""
    try:
        import openrouter
    except ImportError as exc:
        raise RuntimeError("Пакет openrouter не установлен") from exc
    return openrouter
