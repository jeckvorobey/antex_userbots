"""Тесты startup-диагностики каталога OpenRouter."""

import json

import httpx
import pytest

from ai.openrouter_catalog import write_free_models_catalog


@pytest.mark.asyncio
async def test_write_free_models_catalog_filters_sorts_and_writes_connection_codes(tmp_path):
    """Пишет только бесплатные text-output модели в порядке OpenRouter best-first."""
    requests = []

    async def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "z-ai/glm-5.2:free",
                        "name": "GLM 5.2 free",
                        "created": 123,
                        "context_length": 1048576,
                        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
                        "pricing": {"prompt": "0", "completion": "0"},
                        "supported_parameters": ["temperature", "max_tokens"],
                        "top_provider": {"context_length": 1048576, "max_completion_tokens": 256000},
                    },
                    {
                        "id": "paid/model",
                        "name": "Paid",
                        "context_length": 8192,
                        "architecture": {"output_modalities": ["text"]},
                        "pricing": {"prompt": "0.1", "completion": "0", "request": "0"},
                    },
                    {
                        "id": "image/only:free",
                        "name": "Image",
                        "context_length": 8192,
                        "architecture": {"output_modalities": ["image"]},
                        "pricing": {"prompt": "0", "completion": "0", "request": "0"},
                    },
                    {
                        "id": "google/gemma-4-31b-it:free",
                        "name": "Gemma 4 free",
                        "created": 456,
                        "context_length": 262144,
                        "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
                        "pricing": {"prompt": "0", "completion": "0"},
                        "supported_parameters": ["temperature"],
                        "top_provider": {"context_length": 262144, "max_completion_tokens": 8192},
                    },
                ],
                "total_count": 4,
            },
            request=request,
        )

    output_path = tmp_path / "openrouter_free_models.json"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
        result = await write_free_models_catalog(
            api_key="secret-key",
            output_path=output_path,
            http_client=http_client,
        )

    assert result == {
        "status": "ok",
        "models_count": 2,
        "configured_model_checks_count": 0,
        "output_path": str(output_path),
    }
    assert requests[0].url.path == "/api/v1/models"
    assert requests[0].url.params["max_price"] == "0"
    assert requests[0].url.params["max_output_price"] == "0"
    assert requests[0].url.params["output_modalities"] == "text"
    assert requests[0].url.params["sort"] == "intelligence-high-to-low"
    assert requests[0].headers["Authorization"] == "Bearer secret-key"

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["sort"] == "intelligence-high-to-low"
    assert payload["connection_codes"] == [
        "z-ai/glm-5.2:free",
        "google/gemma-4-31b-it:free",
    ]
    assert payload["toml_models_line"] == (
        'models = ["z-ai/glm-5.2:free", "google/gemma-4-31b-it:free"]'
    )
    assert [item["connection_code"] for item in payload["models"]] == payload["connection_codes"]
    assert payload["models"][0]["pricing"]["request"] == "0"
    assert "secret-key" not in output_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_write_free_models_catalog_checks_configured_model_availability(tmp_path):
    """Проверяет configured модели коротким Chat Completions probe."""
    posted_models = []
    probe_timeouts = []

    async def handle(request):
        if request.url.path == "/api/v1/models":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "available/model:free",
                            "architecture": {"output_modalities": ["text"]},
                            "pricing": {"prompt": "0", "completion": "0"},
                        }
                    ],
                    "total_count": 1,
                },
                request=request,
            )

        body = json.loads(request.content)
        posted_models.append(body["model"])
        probe_timeouts.append(request.extensions["timeout"])
        if body["model"] == "available/model:free":
            assert body["messages"] == [{"role": "user", "content": "Ответь только цифрой 1."}]
            assert body["provider"] == {"zdr": False, "allow_fallbacks": True}
            assert body["stream"] is False
            assert body["max_completion_tokens"] == 4
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "1."}}]},
                request=request,
            )
        return httpx.Response(
            404,
            json={
                "error": {
                    "code": "missing-secret-key",
                    "message": "raw provider text secret-key",
                    "metadata": {"error_type": "not_found", "provider_code": "no_route"},
                }
            },
            request=request,
        )

    output_path = tmp_path / "openrouter_free_models.json"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
        result = await write_free_models_catalog(
            api_key="secret-key",
            output_path=output_path,
            configured_models=["available/model:free", "broken/model:free"],
            http_client=http_client,
        )

    assert result == {
        "status": "ok",
        "models_count": 1,
        "configured_model_checks_count": 2,
        "output_path": str(output_path),
    }
    assert posted_models == ["available/model:free", "broken/model:free"]
    assert probe_timeouts == [
        {"connect": 8.0, "read": 8.0, "write": 8.0, "pool": 8.0},
        {"connect": 8.0, "read": 8.0, "write": 8.0, "pool": 8.0},
    ]
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["configured_model_checks"] == [
        {
            "connection_code": "available/model:free",
            "available": True,
            "status_code": 200,
            "response": "1.",
        },
        {
            "connection_code": "broken/model:free",
            "available": False,
            "status_code": 404,
            "error_code": "missing-<redacted_secret>",
            "error_type": "not_found",
            "provider_code": "no_route",
        },
    ]
    serialized = output_path.read_text(encoding="utf-8")
    assert "secret-key" not in serialized
    assert "raw provider text" not in serialized


@pytest.mark.asyncio
async def test_write_free_models_catalog_writes_safe_error_file(tmp_path):
    """При ошибке каталога пишет отдельную безопасную диагностику."""

    async def handle(request):
        return httpx.Response(
            403,
            json={"error": {"code": 403, "message": "Forbidden for secret-key"}},
            request=request,
        )

    output_path = tmp_path / "openrouter_free_models.json"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
        result = await write_free_models_catalog(
            api_key="secret-key",
            output_path=output_path,
            http_client=http_client,
        )

    assert result == {"status": "error", "models_count": 0, "output_path": str(output_path)}
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "error"
    assert payload["error"]["status_code"] == 403
    assert payload["error"]["message"] == "Forbidden for <redacted_secret>"
    assert "secret-key" not in output_path.read_text(encoding="utf-8")
