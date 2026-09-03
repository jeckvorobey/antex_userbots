"""Тесты provider-neutral redaction и safety."""

import pytest

from ai.generation import TextGenerationClient


class FakeGenerationClient(TextGenerationClient):
    """Минимальная реализация интерфейса для проверки общего поведения."""

    async def generate_reply(self, system_prompt, history, user_message):
        return "ok"

    async def start_topic(self, system_prompt, topic):
        return "ok"

    async def close(self):
        return None


def test_generation_client_sanitizes_sensitive_text_for_prompt():
    """Проверяет редактирование invite и секретов до внешнего запроса."""
    client = FakeGenerationClient()
    text = "join https://t.me/+abcdef token=supersecretvalue1234567890abc api_hash: qwerty1234567890qwerty1234567890"

    sanitized = client.sanitize_for_prompt(text)

    assert "t.me/+abcdef" not in sanitized
    assert "supersecretvalue1234567890abc" not in sanitized
    assert "qwerty1234567890qwerty1234567890" not in sanitized
    assert "<redacted_secret>" in sanitized


def test_generation_client_redacts_credential_bearing_urls():
    """Не отправляет внешнему provider URL со встроенными credentials."""
    client = FakeGenerationClient()

    sanitized = client.sanitize_for_prompt(
        "proxy https://short:pwd@example.com/path и http://operator@internal.example/status"
    )

    assert "short" not in sanitized
    assert "pwd" not in sanitized
    assert "operator" not in sanitized
    assert "<redacted_credential_url>" in sanitized


def test_generation_client_rejects_unsafe_output():
    """Проверяет общий safety-гейт перед публикацией."""
    client = FakeGenerationClient(max_output_chars=20, max_mentions_per_message=1)
    public_link_client = FakeGenerationClient(max_output_chars=120, max_mentions_per_message=1)

    assert client.is_output_safe("Нормальный ответ") is True
    assert client.is_output_safe("") is False
    assert public_link_client.is_output_safe("Я бы через https://t.me/tt_exchenge_bot/antex попробовал.") is True
    assert client.is_output_safe("https://t.me/+abcdef") is False
    assert client.is_output_safe("@one @two") is False
    assert client.is_output_safe("Очень длинный ответ, который превышает лимит") is False


@pytest.mark.parametrize(
    "text",
    [
        "Посмотри https://evil.example/phishing",
        "[полезная ссылка](https://evil.example/phishing)",
        "Открой HTTP://evil.example/path",
    ],
)
def test_generation_client_rejects_unapproved_output_urls(text):
    """Не разрешает модели публиковать посторонние URL."""
    client = FakeGenerationClient(max_output_chars=200)

    assert client.is_output_safe(text) is False


def test_generation_client_allows_only_approved_miniapp_url():
    """Сохраняет разрешённый продуктовый Mini App URL, включая пунктуацию."""
    client = FakeGenerationClient(max_output_chars=200)

    assert client.is_output_safe("Попробуй https://t.me/tt_exchenge_bot/antex.") is True


def test_generation_client_sanitizes_history_without_mutation():
    """Проверяет очистку копии истории без изменения входных данных."""
    client = FakeGenerationClient()
    history = [{"role": "user", "text": "token=abcd1234abcd1234abcd1234abcd1234"}]

    sanitized = client.sanitize_history_for_prompt(history)

    assert sanitized[0]["text"] == "token=<redacted_secret>"
    assert history[0]["text"].endswith("abcd1234")


def test_generation_client_renders_history():
    """Проверяет сохранение прежнего формата истории."""
    client = FakeGenerationClient()

    assert client.render_history([{"role": "user", "text": "Привет"}]) == "История диалога:\nuser: Привет"
