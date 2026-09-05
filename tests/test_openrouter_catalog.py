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
@pytest.mark.parametrize("answer", ["Да, доступен", " Да, доступен.\n", "Работаю", "private text secret-key"])
@pytest.mark.parametrize("fail_first", [False, True])
async def test_probes_stop_on_first_text_success(tmp_path, answer, fail_first):
    """Первый непустой текст завершает последовательные проверки без GET каталога."""
    calls = []

    async def handle(request):
        assert request.method == "POST"
        body = json.loads(request.content)
        calls.append(body["model"])
        assert body["messages"] == [{"role": "user", "content": "Ответь только словами: Да, доступен"}]
        assert body["max_completion_tokens"] == 32
        assert request.extensions["timeout"]["read"] == 8.0
        if fail_first and body["model"] == "first:free":
            return httpx.Response(429, json={"error": {"code": 429}})
        return httpx.Response(200, json={"choices": [{"message": {"content": answer}}]})

    path = tmp_path / "report.json"
    path.write_text('{"old_catalog": true}')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        await write_free_models_catalog(api_key="secret-key", output_path=path,
            configured_models=["first:free", "first:free", "second:free", "third:free"], http_client=client)
    assert calls == (["first:free", "second:free"] if fail_first else ["first:free"])
    payload = json.loads(path.read_text())
    assert payload["catalog_fetched"] is False
    assert payload["configured_model_checks"][-1]["available"] is True
    assert "old_catalog" not in payload
    assert "secret-key" not in path.read_text()
    assert "private text" not in path.read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize("catalog_status", [200, 403])
async def test_all_failed_probes_fetch_catalog_last(tmp_path, catalog_status):
    """HTTP ошибки, таймаут и пустые/некорректные ответы ведут к каталогу после POST."""
    calls = []
    models = ["http", "timeout", "empty", "null", "missing", "nontext", "invalid"]

    async def handle(request):
        if request.method == "GET":
            calls.append("catalog")
            return httpx.Response(catalog_status, json={"data": [], "error": {"code": 403}})
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == "http":
            return httpx.Response(404, json={"error": {"code": 404}})
        if model == "timeout":
            raise httpx.ReadTimeout("private detail", request=request)
        if model == "invalid":
            return httpx.Response(200, text="not json")
        if model == "missing":
            return httpx.Response(200, json={"choices": []})
        content = {"empty": " \n", "null": None, "nontext": []}[model]
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    path = tmp_path / "report.json"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        await write_free_models_catalog(api_key="secret-key", output_path=path,
            configured_models=models, http_client=client)
    assert calls == models + ["catalog"]
    payload = json.loads(path.read_text())
    assert len(payload["configured_model_checks"]) == len(models)
    assert all(not row["available"] for row in payload["configured_model_checks"])
    assert "private detail" not in path.read_text()


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
