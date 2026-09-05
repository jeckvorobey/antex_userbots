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
from ai.openrouter import OpenRouterClient


logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_FREE_MODELS_LOG = "logs/openrouter_free_models.json"
OPENROUTER_FREE_MODELS_SORT = "intelligence-high-to-low"
OPENROUTER_MODELS_PAGE_SIZE = 1000
OPENROUTER_MODEL_PROBE_PROMPT_PATH = Path(__file__).parent / "prompts" / "model_probe.md"
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
    ai_client: OpenRouterClient | None = None,
) -> dict[str, Any]:
    """Проверяет генерацию; при всех отказах получает каталог бесплатных моделей."""
    path = Path(output_path)
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(proxy=proxy, timeout=timeout_seconds)
    owns_ai_client = ai_client is None
    generation_client = ai_client or OpenRouterClient(
        api_key=api_key, models=list(configured_models or ()), proxy=proxy,
        request_timeout_seconds=timeout_seconds,
    )
    model_checks: list[dict[str, Any]] = []
    try:
        try:
            model_checks = await _probe_configured_models(
                generation_client,
                api_key=api_key,
                configured_models=list(configured_models or ()),
                timeout_seconds=model_probe_timeout_seconds,
            )
            if any(check["available"] for check in model_checks):
                _write_json(path, {
                    "status": "ok",
                    "generated_at": datetime.now(UTC).isoformat(),
                    "catalog_fetched": False,
                    "configured_model_checks": model_checks,
                })
                logger.info("OpenRouter startup generation succeeded: checks=%s catalog skipped", len(model_checks))
                return {
                    "status": "ok", "models_count": 0,
                    "configured_model_checks_count": len(model_checks), "output_path": str(path),
                }
            models, total_count = await _fetch_all_free_text_models(client, api_key=api_key)
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
            payload["configured_model_checks"] = model_checks
            _write_json(path, payload)
            logger.warning(
                "OpenRouter free models catalog failed: path=%s status=%s message=%r",
                path,
                payload["error"].get("status_code", "unknown"),
                payload["error"].get("message", "unknown"),
            )
            return {"status": "error", "models_count": 0, "output_path": str(path)}
    finally:
        try:
            if owns_ai_client:
                await generation_client.close()
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
    client: OpenRouterClient,
    *,
    api_key: str,
    configured_models: list[str],
    timeout_seconds: float,
) -> list[dict[str, Any]]:
    """Проверяет модели последовательно до первого непустого текстового ответа."""
    models = _unique_models(configured_models)
    if not models:
        return []
    prompt = (await asyncio.to_thread(OPENROUTER_MODEL_PROBE_PROMPT_PATH.read_text, encoding="utf-8")).strip()
    checks = []
    for model in models:
        logger.info("OpenRouter startup request: model=%s prompt=%r",
                    _sanitize_external_scalar(model, api_key=api_key),
                    _sanitize_external_scalar(prompt, api_key=api_key))
        check = await _probe_one_configured_model(
            client, api_key=api_key, model=model, timeout_seconds=timeout_seconds, prompt=prompt,
        )
        checks.append(check)
        logger.info("OpenRouter startup result: model=%s attempt=%s available=%s status=%s",
                    _sanitize_external_scalar(model, api_key=api_key),
                    len(checks), check["available"], check["status_code"])
        if check["available"]:
            break
    return checks


async def _probe_one_configured_model(
    client: OpenRouterClient,
    *,
    api_key: str,
    model: str,
    timeout_seconds: float,
    prompt: str,
) -> dict[str, Any]:
    """Проверяет одну модель через SDK с общим deadline на retries."""
    try:
        async with asyncio.timeout(timeout_seconds):
            answer = await client.probe_model(model, prompt)
        logger.info("OpenRouter startup answer: model=%s answer=%r",
                    _sanitize_external_scalar(model, api_key=api_key),
                    _sanitize_external_scalar(answer, api_key=api_key))
        return {
            "connection_code": model,
            "available": bool(answer),
            "status_code": 200,
            "response": "text_received" if answer else "empty",
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
        "catalog_fetched": True,
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
    status_code = OpenRouterClient._extract_status_code(exc)
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


def _build_probe_error_check(*, model: str, exc: Exception, api_key: str) -> dict[str, Any]:
    """Собирает safe availability result без свободного provider message."""
    status_code = OpenRouterClient._extract_status_code(exc)
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
