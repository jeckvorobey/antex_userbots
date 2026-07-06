"""Тесты для модуля Gemini AI клиента и загрузчика промтов."""

import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai.gemini import GeminiClient, GeminiTemporaryError, PromptLoader


@pytest.fixture(autouse=True)
def inline_to_thread(monkeypatch):
    """Подменяет asyncio.to_thread на синхронную заглушку для быстрых unit-тестов."""

    async def fake_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr("ai.gemini.asyncio.to_thread", fake_to_thread)


async def test_prompt_loader_reads_md_file():
    """Проверяет, что загрузчик читает содержимое .md файла по имени."""
    with tempfile.TemporaryDirectory() as tmpdir:
        prompt_file = Path(tmpdir) / "system.md"
        prompt_file.write_text("Ты полезный ассистент.", encoding="utf-8")

        loader = PromptLoader(prompts_dir=tmpdir)
        content = await loader.load("system")

        assert "Ты полезный ассистент" in content


async def test_prompt_loader_raises_on_missing_file():
    """Проверяет, что FileNotFoundError бросается при отсутствии файла."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PromptLoader(prompts_dir=tmpdir)

        with pytest.raises(FileNotFoundError):
            await loader.load("несуществующий_промт")


async def test_prompt_loader_preserves_full_content():
    """Проверяет, что загрузчик возвращает полное содержимое файла."""
    content = "# Заголовок\n\nПервый абзац.\nВторой абзац."
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.md").write_text(content, encoding="utf-8")

        loader = PromptLoader(prompts_dir=tmpdir)
        result = await loader.load("test")

        assert result == content


def test_runtime_prompt_files_are_committed():
    """Проверяет, что production-промты одного инстанса лежат в репозитории."""
    prompt_files = [
        Path("ai/prompts/system.md"),
        Path("ai/prompts/reply.md"),
        Path("ai/prompts/start_topic.md"),
        Path("ai/prompts/topics.md"),
        Path("ai/prompts/wind_down_hint.md"),
    ]

    for path in prompt_files:
        assert path.exists(), f"Нет prompt-файла: {path}"
        assert path.read_text(encoding="utf-8").strip()


@pytest.mark.asyncio
async def test_prompt_loader_can_read_committed_runtime_prompt():
    """Проверяет, что loader читает реальный runtime prompt."""
    loader = PromptLoader(prompts_dir="ai/prompts")
    system_prompt = await loader.load("system")

    assert "Telegram" in system_prompt


def test_no_prompt_examples_are_required_anymore():
    """Проверяет, что старые шаблоны .example.md удалены из prompt-контракта."""
    assert not list(Path("ai/prompts").glob("**/*.example.md"))


def _prod_persona_files() -> set[str]:
    """Возвращает persona-файлы, объявленные в production TOML."""
    import tomllib

    settings_path = Path("config/settings.prod.toml")
    if not settings_path.exists():
        pytest.skip("Локальный config/settings.prod.toml отсутствует в этом checkout")
    settings_data = tomllib.loads(settings_path.read_text(encoding="utf-8"))
    return {
        bot["persona_file"]
        for bot in settings_data["swarm"]["bots"]
    }


def test_prod_persona_inventory_matches_settings():
    """Проверяет, что committed persona inventory соответствует production settings."""
    configured_personas = _prod_persona_files()
    committed_personas = {
        path.name
        for path in Path("ai/prompts/bots").glob("*.md")
    }

    assert committed_personas == configured_personas


def test_prod_personas_are_detailed_and_structured():
    """Проверяет, что production persona-профили достаточно подробные и структурированные."""
    required_sections = [
        "## Характер",
        "## Манера общения",
        "## Поведение в чате",
        "## Поведение в групповых обсуждениях",
        "## Реакции",
        "## Стиль мышления",
        "## Интересы",
        "## Небольшой жизненный контекст",
        "## Индивидуальные привычки",
        "## Поведение в конфликте",
        "## Ограничения",
        "## Вероятностное поведение",
        "## Взаимоотношения",
        "## Человеческие несовершенства",
    ]

    for persona_file in _prod_persona_files():
        text = (Path("ai/prompts/bots") / persona_file).read_text(encoding="utf-8")

        assert len(text.split()) >= 300, f"Persona слишком короткая: {persona_file}"
        for section in required_sections:
            assert section in text, f"В {persona_file} нет секции {section}"
        assert "никогда не сообщает, что он AI" in text or "никогда не сообщает, что она AI" in text
        assert "не копирует стиль других персонажей" in text
        assert "не превращается в \"идеального помощника\"" in text


def test_prod_personas_are_not_duplicate_templates():
    """Проверяет, что production persona-профили не являются одинаковыми шаблонами."""
    persona_texts = {
        persona_file: (Path("ai/prompts/bots") / persona_file).read_text(encoding="utf-8")
        for persona_file in _prod_persona_files()
    }
    unique_texts = set(persona_texts.values())

    assert len(unique_texts) == len(persona_texts)


def test_shared_topics_are_city_neutral_intents():
    """Проверяет, что общий topics.md не содержит готовые вопросы под один город."""
    topics_path = Path("ai/prompts/topics.md")
    city_markers = {"нячанг", "danang", "da nang", "батум", "batumi"}
    topic_lines = [
        line.strip()
        for line in topics_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#") and line.strip() != "---"
    ]

    assert topic_lines
    assert all("?" not in line for line in topic_lines)
    lowered = "\n".join(topic_lines).lower()
    assert not any(marker in lowered for marker in city_markers)


def test_start_topic_prompt_requires_city_adaptation():
    """Проверяет, что start_topic prompt адаптирует общий intent под город группы."""
    prompt = Path("ai/prompts/start_topic.md").read_text(encoding="utf-8").lower()

    assert "город" in prompt
    assert "не упоминай другой город" in prompt
    assert "не копируй тему дословно" in prompt


def test_important_service_start_topic_prompt_contract():
    """Проверяет prompt-контракт important-service вопроса."""
    prompt = Path("ai/prompts/start_topic.md").read_text(encoding="utf-8")

    assert "important_service_question" in prompt
    assert "question_intent" in prompt
    assert "не упоминай `https://t.me/tt_exchenge_bot/antex`" in prompt
    assert "отсутствует, не добавляй рекламный смысл" in prompt


def test_important_service_reply_prompt_contract():
    """Проверяет prompt-контракт important-service ответа."""
    prompt = Path("ai/prompts/reply.md").read_text(encoding="utf-8")

    assert "important_service_answer" in prompt
    assert "естественно упомяни miniapp-ссылку `https://t.me/tt_exchenge_bot/antex`" in prompt
    assert "каждый раз меняй формулировку" in prompt
    assert "отсутствует, не упоминай `https://t.me/tt_exchenge_bot/antex` специально" in prompt


def test_gemini_client_initializes_with_api_key():
    """Проверяет, что GeminiClient инициализируется и хранит имя модели."""
    client = GeminiClient(api_key="test_key_123", model_name="gemini-1.5-flash")
    assert client.model_name == "gemini-1.5-flash"


def test_gemini_client_default_model():
    """Проверяет дефолтное имя модели при инициализации."""
    client = GeminiClient(api_key="test_key_123")
    assert client.model_name is not None
    assert len(client.model_name) > 0


def test_gemini_client_tracks_fallback_model():
    """Проверяет сохранение имени резервной модели Gemini."""
    client = GeminiClient(
        api_key="test_key_123",
        model_name="gemini-2.5-flash",
        fallback_model_name="gemini-2.5-flash-lite",
    )

    assert client.fallback_model_name == "gemini-2.5-flash-lite"


def test_gemini_client_builds_client_with_proxy(monkeypatch):
    """Проверяет передачу proxy-настроек в новый Gemini SDK."""
    captured: dict[str, object] = {}

    class FakeHttpOptions:
        def __init__(self, **kwargs) -> None:
            captured["http_options_kwargs"] = kwargs

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            captured["client_kwargs"] = kwargs

    fake_types = SimpleNamespace(HttpOptions=FakeHttpOptions)
    fake_genai = SimpleNamespace(Client=FakeClient, types=fake_types)

    monkeypatch.setattr("ai.gemini._import_google_genai", lambda: fake_genai)

    client = GeminiClient(
        api_key="test_key_123",
        model_name="gemini-2.5-flash",
        proxy_url="http://user:pass@127.0.0.1:8080",
    )

    sdk_client = client._get_client()

    assert isinstance(sdk_client, FakeClient)
    assert captured["client_kwargs"]["api_key"] == "test_key_123"
    assert "http_options" in captured["client_kwargs"]
    kwargs = captured["http_options_kwargs"]
    assert kwargs.get("client_args") == {"proxy": "http://user:pass@127.0.0.1:8080"}
    assert kwargs.get("async_client_args") == {"proxy": "http://user:pass@127.0.0.1:8080"}


def test_gemini_client_sanitizes_sensitive_text_for_prompt():
    """Проверяет редактирование invite и секретов перед отправкой в LLM."""
    client = GeminiClient(api_key="test_key_123")

    text = "join https://t.me/+abcdef token=supersecretvalue1234567890abc api_hash: qwerty1234567890qwerty1234567890"
    sanitized = client.sanitize_for_prompt(text)

    assert "t.me/+abcdef" not in sanitized
    assert "supersecretvalue1234567890abc" not in sanitized
    assert "qwerty1234567890qwerty1234567890" not in sanitized
    assert "<redacted_secret>" in sanitized


def test_gemini_client_rejects_unsafe_output():
    """Проверяет safety-гейт перед публикацией текста модели."""
    client = GeminiClient(api_key="test_key_123", max_output_chars=20, max_mentions_per_message=1)
    public_link_client = GeminiClient(api_key="test_key_123", max_output_chars=120, max_mentions_per_message=1)

    assert client.is_output_safe("Нормальный ответ") is True
    assert client.is_output_safe("") is False
    assert public_link_client.is_output_safe("Я бы через https://t.me/tt_exchenge_bot/antex попробовал.") is True
    assert client.is_output_safe("https://t.me/+abcdef") is False
    assert client.is_output_safe("@one @two") is False
    assert client.is_output_safe("Очень длинный ответ, который превышает лимит") is False


@pytest.mark.asyncio
async def test_gemini_client_generate_reply_uses_system_instruction(monkeypatch):
    """Проверяет передачу system instruction и содержимого запроса в SDK."""
    captured: dict[str, object] = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["generate_content_kwargs"] = kwargs
            return SimpleNamespace(text="Ответ модели")

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.models = FakeModels()

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    fake_types = SimpleNamespace(GenerateContentConfig=FakeGenerateContentConfig)
    fake_genai = SimpleNamespace(Client=FakeClient, types=fake_types)

    monkeypatch.setattr("ai.gemini._import_google_genai", lambda: fake_genai)

    client = GeminiClient(api_key="test_key_123", model_name="gemini-2.5-flash")

    result = await client.generate_reply(
        system_prompt="Системная роль",
        history=[{"role": "user", "text": "Привет"}],
        user_message="Как дела?",
    )

    assert result == "Ответ модели"
    assert captured["generate_content_kwargs"]["model"] == "gemini-2.5-flash"
    assert captured["generate_content_kwargs"]["contents"] == (
        "История диалога:\nuser: Привет\n\nПользователь: Как дела?"
    )
    assert (
        captured["generate_content_kwargs"]["config"].kwargs["system_instruction"]
        == "Системная роль"
    )


@pytest.mark.asyncio
async def test_gemini_client_sanitizes_history_and_user_message_before_sdk_call(monkeypatch):
    """Проверяет, что в SDK уходят уже отредактированные тексты."""
    captured: dict[str, object] = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["generate_content_kwargs"] = kwargs
            return SimpleNamespace(text="Ответ модели")

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.models = FakeModels()

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    fake_types = SimpleNamespace(GenerateContentConfig=FakeGenerateContentConfig)
    fake_genai = SimpleNamespace(Client=FakeClient, types=fake_types)

    monkeypatch.setattr("ai.gemini._import_google_genai", lambda: fake_genai)

    client = GeminiClient(api_key="test_key_123", model_name="gemini-2.5-flash")
    await client.generate_reply(
        system_prompt="Системная роль",
        history=[{"role": "user", "text": "token=abcd1234abcd1234abcd1234abcd1234"}],
        user_message="Вот ссылка https://t.me/+secret",
    )

    contents = captured["generate_content_kwargs"]["contents"]
    assert "t.me/+secret" not in contents
    assert "abcd1234abcd1234abcd1234abcd1234" not in contents
    assert "<redacted_secret>" in contents


@pytest.mark.asyncio
async def test_gemini_client_retries_on_temporary_server_error(monkeypatch):
    """Проверяет, что временная ошибка Gemini приводит к повторной попытке."""
    attempts = {"count": 0}

    class FakeServerError(Exception):
        def __init__(self, status_code: int, message: str) -> None:
            super().__init__(message)
            self.status_code = status_code

    class FakeModels:
        def generate_content(self, **kwargs):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise FakeServerError(503, "503 UNAVAILABLE")
            return SimpleNamespace(text="Ответ после повтора")

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.models = FakeModels()

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    fake_types = SimpleNamespace(GenerateContentConfig=FakeGenerateContentConfig)
    fake_genai = SimpleNamespace(Client=FakeClient, types=fake_types)

    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("ai.gemini._import_google_genai", lambda: fake_genai)
    monkeypatch.setattr("ai.gemini.asyncio.sleep", fake_sleep)

    client = GeminiClient(
        api_key="test_key_123",
        model_name="gemini-2.5-flash",
        max_retries=3,
        retry_backoff_seconds=0.5,
        retry_jitter_seconds=0.0,
    )

    result = await client.generate_reply(
        system_prompt="Системная роль",
        history=[],
        user_message="Привет",
    )

    assert result == "Ответ после повтора"
    assert attempts["count"] == 3
    assert delays == [0.5, 1.0]


@pytest.mark.asyncio
async def test_gemini_client_raises_temporary_error_after_retry_limit(monkeypatch):
    """Проверяет, что после исчерпания повторов поднимается специализированная ошибка."""

    class FakeServerError(Exception):
        def __init__(self, status_code: int, message: str) -> None:
            super().__init__(message)
            self.status_code = status_code

    class FakeModels:
        def generate_content(self, **kwargs):
            raise FakeServerError(503, "503 UNAVAILABLE")

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.models = FakeModels()

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    fake_types = SimpleNamespace(GenerateContentConfig=FakeGenerateContentConfig)
    fake_genai = SimpleNamespace(Client=FakeClient, types=fake_types)

    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("ai.gemini._import_google_genai", lambda: fake_genai)
    monkeypatch.setattr("ai.gemini.asyncio.sleep", fake_sleep)

    client = GeminiClient(
        api_key="test_key_123",
        model_name="gemini-2.5-flash",
        max_retries=2,
        retry_backoff_seconds=0.5,
        retry_jitter_seconds=0.0,
    )

    with pytest.raises(GeminiTemporaryError):
        await client.generate_reply(
            system_prompt="Системная роль",
            history=[],
            user_message="Привет",
        )

    assert delays == [0.5]


@pytest.mark.asyncio
async def test_gemini_client_switches_to_fallback_model_after_retry_limit(monkeypatch):
    """Проверяет переключение на резервную модель после исчерпания повторов основной."""
    attempts: list[str] = []

    class FakeServerError(Exception):
        def __init__(self, status_code: int, message: str) -> None:
            super().__init__(message)
            self.status_code = status_code

    class FakeModels:
        def generate_content(self, **kwargs):
            model = kwargs["model"]
            attempts.append(model)
            if model == "gemini-2.5-flash":
                raise FakeServerError(503, "503 UNAVAILABLE")
            return SimpleNamespace(text="Ответ резервной модели")

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.models = FakeModels()

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    fake_types = SimpleNamespace(GenerateContentConfig=FakeGenerateContentConfig)
    fake_genai = SimpleNamespace(Client=FakeClient, types=fake_types)

    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("ai.gemini._import_google_genai", lambda: fake_genai)
    monkeypatch.setattr("ai.gemini.asyncio.sleep", fake_sleep)

    client = GeminiClient(
        api_key="test_key_123",
        model_name="gemini-2.5-flash",
        fallback_model_name="gemini-2.5-flash-lite",
        max_retries=2,
        retry_backoff_seconds=0.5,
        retry_jitter_seconds=0.0,
    )

    result = await client.generate_reply(
        system_prompt="Системная роль",
        history=[],
        user_message="Привет",
    )

    assert result == "Ответ резервной модели"
    assert attempts == [
        "gemini-2.5-flash",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]
    assert delays == [0.5]


@pytest.mark.asyncio
async def test_gemini_client_adds_jitter_to_retry_delay(monkeypatch):
    """Проверяет добавление jitter к экспоненциальной задержке повтора."""

    class FakeServerError(Exception):
        def __init__(self, status_code: int, message: str) -> None:
            super().__init__(message)
            self.status_code = status_code

    class FakeModels:
        def generate_content(self, **kwargs):
            raise FakeServerError(503, "503 UNAVAILABLE")

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.models = FakeModels()

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    fake_types = SimpleNamespace(GenerateContentConfig=FakeGenerateContentConfig)
    fake_genai = SimpleNamespace(Client=FakeClient, types=fake_types)

    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("ai.gemini._import_google_genai", lambda: fake_genai)
    monkeypatch.setattr("ai.gemini.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("ai.gemini.random.uniform", lambda start, end: 0.25)

    client = GeminiClient(
        api_key="test_key_123",
        model_name="gemini-2.5-flash",
        max_retries=2,
        retry_backoff_seconds=0.5,
        retry_jitter_seconds=0.5,
    )

    with pytest.raises(GeminiTemporaryError):
        await client.generate_reply(
            system_prompt="Системная роль",
            history=[],
            user_message="Привет",
        )

    assert delays == [0.75]


@pytest.mark.asyncio
async def test_gemini_client_retries_on_request_timeout(monkeypatch):
    """Проверяет, что таймаут запроса считается временной ошибкой и ретраится."""

    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(text="Ответ после таймаута")

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.models = FakeModels()

    class FakeGenerateContentConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    fake_types = SimpleNamespace(GenerateContentConfig=FakeGenerateContentConfig)
    fake_genai = SimpleNamespace(Client=FakeClient, types=fake_types)

    delays: list[float] = []
    wait_for_calls = {"count": 0}

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    async def fake_wait_for(awaitable, timeout: float):
        wait_for_calls["count"] += 1
        if wait_for_calls["count"] == 1:
            awaitable.close()
            raise TimeoutError
        return await awaitable

    monkeypatch.setattr("ai.gemini._import_google_genai", lambda: fake_genai)
    monkeypatch.setattr("ai.gemini.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("ai.gemini.asyncio.wait_for", fake_wait_for)

    client = GeminiClient(
        api_key="test_key_123",
        model_name="gemini-2.5-flash",
        max_retries=2,
        retry_backoff_seconds=0.5,
        retry_jitter_seconds=0.0,
        request_timeout_seconds=15.0,
    )

    result = await client.generate_reply(
        system_prompt="Системная роль",
        history=[],
        user_message="Привет",
    )

    assert result == "Ответ после таймаута"
    assert delays == [0.5]
    assert wait_for_calls["count"] == 2
