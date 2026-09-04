"""Fake-SDK тесты OpenRouter adapter."""

import logging
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from ai.generation import GenerationError, TemporaryGenerationError
from ai.openrouter import OpenRouterClient


class FakeBackoff:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeRetry:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeChat:
    def __init__(self, response=None, error=None):
        self.response = response or SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=" Ответ модели "))]
        )
        self.error = error
        self.calls = []

    async def send_async(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeSdkClient:
    def __init__(self, chat=None, **kwargs):
        self.chat = chat or FakeChat()
        self.kwargs = kwargs
        self.exit_calls = 0

    async def __aexit__(self, exc_type, exc, traceback):
        self.exit_calls += 1


def install_fake_sdk(monkeypatch, *, chat=None):
    """Подменяет SDK и возвращает список созданных клиентов."""
    created = []

    def factory(**kwargs):
        client = FakeSdkClient(chat=chat, **kwargs)
        created.append(client)
        return client

    fake_module = SimpleNamespace(
        OpenRouter=factory,
        utils=SimpleNamespace(BackoffStrategy=FakeBackoff, RetryConfig=FakeRetry),
    )
    monkeypatch.setattr("ai.openrouter._import_openrouter", lambda: fake_module)
    return created


@pytest.mark.asyncio
async def test_openrouter_sends_ordered_models_without_zdr(monkeypatch):
    """Проверяет request contract локального режима без ZDR."""
    chat = FakeChat()
    created = install_fake_sdk(monkeypatch, chat=chat)
    client = OpenRouterClient(api_key="secret-key", models=["vendor/primary", "vendor/fallback"])

    result = await client.generate_reply(
        system_prompt="Системная роль",
        history=[{"role": "user", "text": "Привет"}],
        user_message="Как дела?",
    )

    assert result == "Ответ модели"
    request = chat.calls[0]
    assert request["models"] == ["vendor/primary", "vendor/fallback"]
    assert request["messages"] == [
        {"role": "system", "content": "Системная роль"},
        {"role": "user", "content": "История диалога:\nuser: Привет\n\nПользователь: Как дела?"},
    ]
    assert request["provider"] == {
        "zdr": False,
        "allow_fallbacks": True,
    }
    assert request["stream"] is False
    assert request["max_completion_tokens"] == 256
    assert "temperature" not in request
    assert created[0].kwargs["api_key"] == "secret-key"
    assert created[0].kwargs["timeout_ms"] == 45000


@pytest.mark.asyncio
async def test_openrouter_forwards_temperature_and_redacts_topic(monkeypatch):
    """Проверяет optional temperature и очистку topic."""
    chat = FakeChat()
    install_fake_sdk(monkeypatch, chat=chat)
    client = OpenRouterClient(
        api_key="secret-key",
        models=["vendor/primary", "vendor/fallback"],
        temperature=0.6,
    )

    await client.start_topic("Роль", "token=abcd1234abcd1234abcd1234abcd1234")

    request = chat.calls[0]
    assert request["temperature"] == 0.6
    assert request["messages"][1]["content"] == "Тема разговора: token=<redacted_secret>"


def test_openrouter_builds_bounded_sdk_retry_config(monkeypatch):
    """Проверяет timeout и параметры retry официального SDK."""
    created = install_fake_sdk(monkeypatch)
    client = OpenRouterClient(api_key="key", models=["one", "two"])

    client._get_client()

    retry = created[0].kwargs["retry_config"]
    assert retry.strategy == "backoff"
    assert retry.retry_connection_errors is True
    assert retry.status_codes_override == ["408", "429", "5XX", "524", "529"]
    assert retry.backoff.initial_interval == 500
    assert retry.backoff.max_interval == 5000
    assert retry.backoff.max_elapsed_time == 15000
    assert retry.backoff.jitter_ms == 300


@pytest.mark.asyncio
async def test_openrouter_uses_and_closes_proxy_transport_once(monkeypatch):
    """Проверяет передачу proxy в HTTPX и управляемое закрытие."""
    created_http = []

    class FakeHttpClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.close_calls = 0
            created_http.append(self)

        async def aclose(self):
            self.close_calls += 1

    monkeypatch.setattr("ai.openrouter.httpx.AsyncClient", FakeHttpClient)
    created_sdk = install_fake_sdk(monkeypatch)
    client = OpenRouterClient(
        api_key="key",
        models=["one", "two"],
        proxy="http://user:pass@127.0.0.1:8080",
    )
    client._get_client()

    assert created_http[0].kwargs["proxy"] == "http://user:pass@127.0.0.1:8080"
    assert created_sdk[0].kwargs["async_client"] is created_http[0]
    await client.close()
    await client.close()
    assert created_sdk[0].exit_calls == 1
    assert created_http[0].close_calls == 1


@pytest.mark.asyncio
async def test_openrouter_closes_direct_sdk_transport_once(monkeypatch):
    """Проверяет закрытие созданного SDK direct transport."""
    created_sdk = install_fake_sdk(monkeypatch)
    client = OpenRouterClient(api_key="key", models=["one", "two"])
    client._get_client()

    await client.close()
    await client.close()

    assert created_sdk[0].exit_calls == 1


@pytest.mark.asyncio
async def test_openrouter_closes_proxy_transport_when_sdk_exit_fails():
    """Owned HTTPX transport закрывается даже при ошибке SDK shutdown."""
    sdk_client = SimpleNamespace(__aexit__=AsyncMock(side_effect=RuntimeError("sdk close failed")))
    http_client = SimpleNamespace(aclose=AsyncMock())
    client = OpenRouterClient(api_key="secret-key", models=["vendor/primary", "vendor/fallback"])
    client._client = sdk_client
    client._http_client = http_client

    with pytest.raises(RuntimeError, match="sdk close failed"):
        await client.close()

    http_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [None, "", "   ", ["not text"]])
async def test_openrouter_rejects_empty_or_non_text_response(monkeypatch, content):
    """Проверяет fail-closed response parsing."""
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    install_fake_sdk(monkeypatch, chat=FakeChat(response=response))
    client = OpenRouterClient(api_key="key", models=["one", "two"])

    with pytest.raises(GenerationError):
        await client.start_topic("Роль", "Тема")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [408, 429, 500, 503, 524, 529])
async def test_openrouter_classifies_retryable_status_as_temporary(monkeypatch, status):
    """Проверяет классификацию исчерпанных временных ошибок."""
    error = RuntimeError("raw provider payload with secret-key")
    error.status_code = status
    install_fake_sdk(monkeypatch, chat=FakeChat(error=error))
    client = OpenRouterClient(api_key="secret-key", models=["one", "two"])

    with pytest.raises(TemporaryGenerationError):
        await client.start_topic("Роль", "Тема")


@pytest.mark.asyncio
async def test_openrouter_classifies_connection_error_as_temporary(monkeypatch):
    """Проверяет классификацию transport error."""
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    install_fake_sdk(monkeypatch, chat=FakeChat(error=httpx.ConnectError("private detail", request=request)))
    client = OpenRouterClient(api_key="key", models=["one", "two"])

    with pytest.raises(TemporaryGenerationError):
        await client.start_topic("Роль", "Тема")


@pytest.mark.asyncio
async def test_openrouter_logs_no_raw_error_or_credentials(monkeypatch, caplog):
    """Проверяет безопасное категорийное логирование ошибок и proxy."""
    error = RuntimeError("raw provider payload secret-key proxy-pass")
    error.status_code = 400
    install_fake_sdk(monkeypatch, chat=FakeChat(error=error))
    client = OpenRouterClient(
        api_key="secret-key",
        models=["one", "two"],
        proxy="http://user:proxy-pass@127.0.0.1:8080",
    )

    with caplog.at_level(logging.WARNING), pytest.raises(GenerationError) as caught:
        await client.start_topic("private prompt", "private topic")

    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True
    logs = caplog.text
    assert "status=400" in logs
    assert "secret-key" not in logs
    assert "proxy-pass" not in logs
    assert "private prompt" not in logs
    assert "private topic" not in logs
    assert "raw provider payload" not in logs


@pytest.mark.asyncio
async def test_openrouter_logs_safe_error_body_details(monkeypatch, caplog):
    """Проверяет безопасные диагностические поля из OpenRouter error body."""
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(
        404,
        json={
            "error": {
                "code": "provider_sk-or-v1-secret1234567890abcd",
                "message": "No endpoints found for private prompt private topic sk-or-v1-secret1234567890abcd",
                "metadata": {
                    "error_type": "not_found",
                    "provider_code": "no_available_endpoint",
                },
            }
        },
        request=request,
    )
    error = httpx.HTTPStatusError("raw provider payload", request=request, response=response)
    install_fake_sdk(monkeypatch, chat=FakeChat(error=error))
    client = OpenRouterClient(
        api_key="sk-or-v1-secret1234567890abcd",
        models=["one", "two"],
    )

    with caplog.at_level(logging.WARNING), pytest.raises(GenerationError):
        await client.start_topic("private prompt", "private topic")

    logs = caplog.text
    assert "status=404" in logs
    assert "openrouter_error_code=provider_<redacted_secret>" in logs
    assert "openrouter_error_type=not_found" in logs
    assert "openrouter_provider_code=no_available_endpoint" in logs
    assert "openrouter_error_message" not in logs
    assert "No endpoints found" not in logs
    assert "sk-or-v1-secret1234567890abcd" not in logs
    assert "private prompt" not in logs
    assert "private topic" not in logs
    assert "raw provider payload" not in logs


@pytest.mark.asyncio
async def test_openrouter_adapter_is_compatible_with_installed_sdk(monkeypatch):
    """Проверяет сериализацию запроса реальной зафиксированной версией SDK."""
    captured = {}

    async def handle(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "generation-test",
                "object": "chat.completion",
                "created": 1,
                "model": "vendor/primary",
                "system_fingerprint": None,
                "choices": [
                    {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "SDK ok"}}
                ],
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    monkeypatch.setattr("ai.openrouter.httpx.AsyncClient", lambda **_kwargs: http_client)
    client = OpenRouterClient(
        api_key="test-key",
        models=["vendor/primary", "vendor/fallback"],
        proxy="http://127.0.0.1:8080",
    )

    result = await client.start_topic("Роль", "Тема")
    await client.close()

    assert result == "SDK ok"
    assert captured["body"]["models"] == ["vendor/primary", "vendor/fallback"]
    assert captured["body"]["provider"] == {"zdr": False, "allow_fallbacks": True}
