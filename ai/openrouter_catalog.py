"""Startup-диагностика доступных бесплатных OpenRouter моделей."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx

from ai.generation import LONG_SECRET_RE


logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_FREE_MODELS_LOG = "logs/openrouter_free_models.json"
OPENROUTER_FREE_MODELS_SORT = "intelligence-high-to-low"
OPENROUTER_MODELS_PAGE_SIZE = 1000
OPENROUTER_MODEL_PROBE_PROMPT = "Ответь только цифрой 1."
OPENROUTER_MODEL_PROBE_TIMEOUT_SECONDS = 8.0


async def write_free_models_catalog(
    *,
    api_key: str,
    output_path: str | Path = OPENROUTER_FREE_MODELS_LOG,
    proxy: str | None = None,
    timeout_seconds: float = 45.0,
    model_probe_timeout_seconds: float = OPENROUTER_MODEL_PROBE_TIMEOUT_SECONDS,
    configured_models: list[str] | tuple[str, ...] | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Получает бесплатные text-output модели OpenRouter и пишет отдельный diagnostic-файл."""
    path = Path(output_path)
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(proxy=proxy, timeout=timeout_seconds)
    try:
        try:
            models, total_count = await _fetch_all_free_text_models(client, api_key=api_key)
            model_checks = await _probe_configured_models(
                client,
                api_key=api_key,
                configured_models=list(configured_models or ()),
                timeout_seconds=model_probe_timeout_seconds,
            )
            payload = _build_success_payload(
                models=models,
                total_count=total_count,
                configured_model_checks=model_checks,
            )
            _write_json(path, payload)
            logger.info(
                "OpenRouter free models catalog written: path=%s models=%s configured_model_checks=%s",
                path,
                len(models),
                len(model_checks),
            )
            return {
                "status": "ok",
                "models_count": len(models),
                "configured_model_checks_count": len(model_checks),
                "output_path": str(path),
            }
        except Exception as exc:
            payload = _build_error_payload(exc=exc, api_key=api_key)
            _write_json(path, payload)
            logger.warning(
                "OpenRouter free models catalog failed: path=%s status=%s message=%r",
                path,
                payload["error"].get("status_code", "unknown"),
                payload["error"].get("message", "unknown"),
            )
            return {"status": "error", "models_count": 0, "output_path": str(path)}
    finally:
        if owns_client:
            await client.aclose()


async def _fetch_all_free_text_models(client: httpx.AsyncClient, *, api_key: str) -> tuple[list[dict[str, Any]], int]:
    """Читает все страницы каталога OpenRouter с server-side сортировкой."""
    headers = {"Authorization": f"Bearer {api_key}"}
    params: dict[str, Any] = {
        "output_modalities": "text",
        "max_price": 0,
        "max_output_price": 0,
        "sort": OPENROUTER_FREE_MODELS_SORT,
        "limit": OPENROUTER_MODELS_PAGE_SIZE,
        "offset": 0,
    }
    collected: list[dict[str, Any]] = []
    total_count = 0

    while True:
        response = await client.get(OPENROUTER_MODELS_URL, headers=headers, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("OpenRouter models response is not an object")
        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError("OpenRouter models response has no data list")
        total_count = _safe_int(payload.get("total_count"), default=len(data))
        collected.extend(item for item in data if isinstance(item, dict))
        if len(collected) >= total_count or len(data) < OPENROUTER_MODELS_PAGE_SIZE:
            break
        params["offset"] = int(params["offset"]) + OPENROUTER_MODELS_PAGE_SIZE

    return [_normalize_model(item) for item in collected if _is_free_text_model(item)], total_count


async def _probe_configured_models(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    configured_models: list[str],
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    """Проверяет каждую configured модель коротким безопасным Chat Completions запросом."""
    models = _unique_models(configured_models)
    return list(
        await asyncio.gather(
            *(
                _probe_one_configured_model(
                    client,
                    api_key=api_key,
                    model=model,
                    timeout_seconds=timeout_seconds,
                )
                for model in models
            )
        )
    )


async def _probe_one_configured_model(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    model: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Проверяет одну configured модель коротким bounded Chat Completions запросом."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        response = await client.post(
            OPENROUTER_CHAT_COMPLETIONS_URL,
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": OPENROUTER_MODEL_PROBE_PROMPT}],
                "provider": {"zdr": False, "allow_fallbacks": True},
                "stream": False,
                "max_completion_tokens": 4,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        answer = _extract_probe_answer(body)
        return {
            "connection_code": model,
            "available": answer in {"1", "да", "yes", "true"},
            "status_code": response.status_code,
            "response": answer or "empty",
        }
    except Exception as exc:
        return _build_probe_error_check(model=model, exc=exc, api_key=api_key)


def _unique_models(configured_models: list[str]) -> list[str]:
    """Оставляет configured модели в порядке конфига без дублей."""
    models: list[str] = []
    seen: set[str] = set()
    for model in configured_models:
        if model in seen:
            continue
        seen.add(model)
        models.append(model)
    return models


def _build_success_payload(
    *,
    models: list[dict[str, Any]],
    total_count: int,
    configured_model_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Собирает operator-friendly JSON для диагностики и копирования TOML."""
    connection_codes = [model["connection_code"] for model in models]
    return {
        "status": "ok",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_url": OPENROUTER_MODELS_URL,
        "sort": OPENROUTER_FREE_MODELS_SORT,
        "filters": {
            "output_modalities": "text",
            "max_price": 0,
            "max_output_price": 0,
        },
        "total_count": total_count,
        "models_count": len(models),
        "configured_model_checks": configured_model_checks,
        "connection_codes": connection_codes,
        "toml_models_line": _format_toml_models_line(connection_codes),
        "models": models,
    }


def _build_error_payload(*, exc: Exception, api_key: str) -> dict[str, Any]:
    """Собирает безопасный diagnostic JSON при ошибке каталога."""
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    return {
        "status": "error",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_url": OPENROUTER_MODELS_URL,
        "sort": OPENROUTER_FREE_MODELS_SORT,
        "models_count": 0,
        "error": {
            "status_code": status_code if isinstance(status_code, int) else "unknown",
            "message": _extract_safe_error_message(exc, api_key=api_key),
        },
    }


def _extract_probe_answer(payload: Any) -> str:
    """Достаёт короткий ответ probe-запроса из Chat Completions response."""
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""
    message = first_choice.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return " ".join(content.strip().lower().split())[:20] if isinstance(content, str) else ""


def _build_probe_error_check(*, model: str, exc: Exception, api_key: str) -> dict[str, Any]:
    """Собирает safe availability result без свободного provider message."""
    status_code = getattr(getattr(exc, "response", None), "status_code", None)
    error_payload = _extract_error_payload(exc)
    return {
        "connection_code": model,
        "available": False,
        "status_code": status_code if isinstance(status_code, int) else "unknown",
        "error_code": _sanitize_external_scalar(error_payload.get("code"), api_key=api_key),
        "error_type": _sanitize_external_scalar(error_payload.get("error_type"), api_key=api_key),
        "provider_code": _sanitize_external_scalar(error_payload.get("provider_code"), api_key=api_key),
    }


def _extract_error_payload(exc: Exception) -> dict[str, Any]:
    """Извлекает только whitelisted поля error body."""
    response = getattr(exc, "response", None)
    parse_json = getattr(response, "json", None)
    if not callable(parse_json):
        return {}
    try:
        payload = parse_json()
    except Exception:
        return {}
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return {}
    metadata = error.get("metadata")
    return {
        "code": error.get("code"),
        "error_type": metadata.get("error_type") if isinstance(metadata, dict) else None,
        "provider_code": metadata.get("provider_code") if isinstance(metadata, dict) else None,
    }


def _sanitize_external_scalar(value: Any, *, api_key: str) -> str:
    """Нормализует внешнее diagnostic-поле перед записью в файл."""
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str) or not value:
        return "unknown"
    sanitized = value.replace(api_key, "<redacted_secret>") if api_key else value
    sanitized = LONG_SECRET_RE.sub("<redacted_secret>", sanitized)
    sanitized = " ".join(sanitized.split())
    return sanitized[:80] if sanitized else "unknown"


def _normalize_model(model: dict[str, Any]) -> dict[str, Any]:
    """Оставляет только безопасные поля каталога, полезные оператору."""
    model_id = str(model.get("id", ""))
    pricing = model.get("pricing") if isinstance(model.get("pricing"), dict) else {}
    architecture = model.get("architecture") if isinstance(model.get("architecture"), dict) else {}
    top_provider = model.get("top_provider") if isinstance(model.get("top_provider"), dict) else {}
    return {
        "connection_code": model_id,
        "name": model.get("name"),
        "context_length": _safe_int(model.get("context_length"), default=0),
        "top_provider_context_length": _safe_int(top_provider.get("context_length"), default=0),
        "max_completion_tokens": _safe_int(top_provider.get("max_completion_tokens"), default=0),
        "input_modalities": architecture.get("input_modalities") or [],
        "output_modalities": architecture.get("output_modalities") or [],
        "supported_parameters": model.get("supported_parameters") or [],
        "pricing": {
            "prompt": str(pricing.get("prompt", "unknown")),
            "completion": str(pricing.get("completion", "unknown")),
            "request": str(pricing.get("request", "0")),
        },
        "created": model.get("created"),
    }


def _is_free_text_model(model: dict[str, Any]) -> bool:
    """Проверяет бесплатность и text-output локально, независимо от query-фильтров."""
    model_id = model.get("id")
    if not isinstance(model_id, str) or not model_id:
        return False
    architecture = model.get("architecture")
    output_modalities = architecture.get("output_modalities") if isinstance(architecture, dict) else None
    if "text" not in (output_modalities or []):
        return False
    pricing = model.get("pricing")
    if not isinstance(pricing, dict):
        return False
    return (
        _is_zero_price(pricing.get("prompt"))
        and _is_zero_price(pricing.get("completion"))
        and _is_zero_price(pricing.get("request", "0"))
    )


def _is_zero_price(value: Any) -> bool:
    """Сравнивает pricing values OpenRouter как decimal strings."""
    try:
        return Decimal(str(value)) == 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def _safe_int(value: Any, *, default: int) -> int:
    """Безопасно нормализует числовые поля каталога."""
    return value if isinstance(value, int) else default


def _format_toml_models_line(model_ids: list[str]) -> str:
    """Формирует строку для `[openrouter] models = [...]`."""
    encoded = ", ".join(json.dumps(model_id, ensure_ascii=False) for model_id in model_ids)
    return f"models = [{encoded}]"


def _extract_safe_error_message(exc: Exception, *, api_key: str) -> str:
    """Достаёт OpenRouter error.message и редактирует секреты."""
    response = getattr(exc, "response", None)
    parse_json = getattr(response, "json", None)
    message = ""
    if callable(parse_json):
        try:
            payload = parse_json()
        except Exception:
            payload = None
        error = payload.get("error") if isinstance(payload, dict) else None
        raw_message = error.get("message") if isinstance(error, dict) else None
        if isinstance(raw_message, str):
            message = raw_message
    if not message:
        message = str(exc)
    if api_key:
        message = message.replace(api_key, "<redacted_secret>")
    message = LONG_SECRET_RE.sub("<redacted_secret>", message)
    return " ".join(message.split())[:300]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Атомарно записывает diagnostic JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)
