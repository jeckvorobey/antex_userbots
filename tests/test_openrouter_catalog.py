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

    assert result == {"status": "ok", "models_count": 2, "output_path": str(output_path)}
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
