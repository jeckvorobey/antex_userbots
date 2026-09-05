"""Тесты startup-диагностики каталога OpenRouter."""

import json
import asyncio
import logging
from types import SimpleNamespace

from tests.test_openrouter import install_fake_sdk

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
        "generation_available": False,
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
@pytest.mark.parametrize("answer", ["Да, работаю", " Работаю.\n", "private text secret-key"])
@pytest.mark.parametrize("fail_first", [False, True])
async def test_probes_stop_on_first_text_success(tmp_path, monkeypatch, caplog, answer, fail_first):
    """Реальный adapter вызывает SDK; лог виден, каталог и сырой JSON исключены."""
    calls = []

    async def send_async(**body):
        calls.append(body["models"])
        assert body["messages"][-1]["content"] == "Ответь только словами: Да, работаю"
        assert body["max_completion_tokens"] == 256
        assert body["provider"] == {"zdr": False, "data_collection": "deny", "allow_fallbacks": True}
        if fail_first and body["models"] == ["first:free"]:
            error = RuntimeError("private failure secret-key")
            error.status_code = 429
            raise error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer))])

    created = install_fake_sdk(monkeypatch, chat=SimpleNamespace(send_async=send_async))
    async def handle(request):
        pytest.fail("Каталог после успеха запрашиваться не должен")

    path = tmp_path / "report.json"
    with caplog.at_level(logging.INFO):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            await write_free_models_catalog(api_key="secret-key", output_path=path,
                configured_models=["first:free", "first:free", "second:free", "third:free"], http_client=client)
    assert calls == ([["first:free"], ["second:free"]] if fail_first else [["first:free"]])
    assert len(created) == 1 and created[0].exit_calls == 1
    assert "model=first:free" in caplog.text
    assert "Ответь только словами: Да, работаю" in caplog.text
    assert answer.strip().replace("secret-key", "<redacted_secret>") in caplog.text
    if fail_first:
        assert "status=429" in caplog.text
        assert any(record.levelno == logging.ERROR and "startup result:" in record.message for record in caplog.records)
    assert "secret-key" not in caplog.text
    assert "private failure" not in caplog.text
    payload = json.loads(path.read_text())
    assert payload["generation_available"] is True
    assert payload["catalog_fetched"] is False
    assert payload["configured_model_checks"][-1]["available"] is True
    assert "secret-key" not in path.read_text()
    assert "private text" not in path.read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize("catalog_status", [200, 403])
async def test_all_failed_probes_fetch_catalog_last(tmp_path, monkeypatch, catalog_status):
    """Ошибки SDK, deadline и пустые ответы проверяются до GET каталога."""
    calls = []
    models = ["http", "timeout", "empty", "null", "missing", "nontext"]

    async def send_async(**body):
        model = body["models"][0]
        calls.append(model)
        if model == "http":
            error = RuntimeError("private detail")
            error.status_code = 404
            raise error
        if model == "timeout":
            await asyncio.sleep(1)
        if model == "missing":
            return SimpleNamespace(choices=[])
        content = {"empty": " \n", "null": None, "nontext": []}[model]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    created = install_fake_sdk(monkeypatch, chat=SimpleNamespace(send_async=send_async))
    async def handle(request):
        assert request.method == "GET"
        calls.append("catalog")
        return httpx.Response(catalog_status, json={"data": [], "error": {"code": 403}})

    path = tmp_path / "report.json"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        await write_free_models_catalog(api_key="secret-key", output_path=path,
            configured_models=models, http_client=client, model_probe_timeout_seconds=0.01)
    assert calls == models + ["catalog"]
    assert created[0].exit_calls == 1
    payload = json.loads(path.read_text())
    assert payload["generation_available"] is False
    assert len(payload["configured_model_checks"]) == len(models)
    assert all(not row["available"] for row in payload["configured_model_checks"])
    assert payload["configured_model_checks"][0]["status_code"] == 404
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

    assert result == {"status": "error", "generation_available": False, "models_count": 0, "output_path": str(output_path)}
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "error"
    assert payload["error"]["status_code"] == 403
    assert payload["error"]["message"] == "Forbidden for <redacted_secret>"
    assert "secret-key" not in output_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_shared_client_keeps_configuration_and_remains_open(tmp_path, monkeypatch):
    """Startup и бот используют один SDK с настройками runtime без мутации models."""
    from ai.openrouter import OpenRouterClient
    from tests.test_openrouter import FakeChat

    chat = FakeChat()
    created = install_fake_sdk(monkeypatch, chat=chat)
    client = OpenRouterClient(api_key="secret-key", models=["one", "two"],
                              temperature=0.42, request_timeout_seconds=12,
                              retry_max_elapsed_time_ms=4321)
    async def handle(request):
        pytest.fail("Каталог не нужен")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
        await write_free_models_catalog(api_key="secret-key", configured_models=client.models,
            ai_client=client, http_client=http_client, output_path=tmp_path / "report.json")
    assert client.models == ["one", "two"]
    assert created[0].exit_calls == 0
    await client.start_topic("system", "topic")
    assert len(created) == 1
    assert chat.calls[0]["models"] == ["one"]
    assert chat.calls[1]["models"] == ["one", "two"]
    for call in chat.calls:
        assert call["temperature"] == 0.42
        assert call["max_completion_tokens"] == 256
    assert created[0].kwargs["timeout_ms"] == 12000
    assert created[0].kwargs["retry_config"].backoff.max_elapsed_time == 4321
    await client.close()
    assert created[0].exit_calls == 1


def test_sdk_error_preserves_safe_provider_details():
    """Настоящее SDK исключение сохраняет whitelist, скрывая ключ и raw message."""
    from openrouter.errors import OpenRouterError
    from ai.openrouter_catalog import _build_probe_error_check

    response = httpx.Response(429, json={"error": {
        "code": 429, "message": "private raw detail secret-key",
        "metadata": {"error_type": "limit secret-key", "provider_code": "rate_limit"},
    }})
    result = _build_probe_error_check(model="model", api_key="secret-key",
                                      exc=OpenRouterError("failure", response))
    assert result["status_code"] == 429
    assert result["error_code"] == "429"
    assert result["error_type"] == "limit <redacted_secret>"
    assert result["provider_code"] == "rate_limit"
    assert "secret-key" not in json.dumps(result)
    assert "private raw detail" not in json.dumps(result)


@pytest.mark.asyncio
async def test_report_write_failure_preserves_generation_readiness(tmp_path, monkeypatch):
    """Недоступный диск не отменяет уже подтверждённую генерацию."""
    from tests.test_openrouter import FakeChat
    created = install_fake_sdk(monkeypatch, chat=FakeChat())
    def fail_write(*args):
        raise PermissionError("report directory unavailable")
    monkeypatch.setattr("ai.openrouter_catalog._write_json", fail_write)
    async def handle(request):
        pytest.fail("После успешной генерации каталог не нужен")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http_client:
        result = await write_free_models_catalog(api_key="test-key", configured_models=["one"],
            http_client=http_client, output_path=tmp_path / "report.json")
    assert result["generation_available"] is True
    assert result["status"] == "error"
    assert created[0].exit_calls == 1


@pytest.mark.asyncio
async def test_default_probe_deadline_uses_configured_request_timeout(tmp_path, monkeypatch):
    """Startup использует настроенный timeout обычной генерации."""
    from unittest.mock import AsyncMock
    probe = AsyncMock(return_value=[{"available": True}])
    monkeypatch.setattr("ai.openrouter_catalog._probe_configured_models", probe)
    async with httpx.AsyncClient() as http_client:
        await write_free_models_catalog(api_key="key", configured_models=["one"],
            timeout_seconds=37, http_client=http_client, output_path=tmp_path / "report.json")
    assert probe.call_args.kwargs["timeout_seconds"] == 37
