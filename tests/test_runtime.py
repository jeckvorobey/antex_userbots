"""Тесты runtime-слоя swarm и bootstrap run.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import SecretStr

from core.config import Settings
from telethon.errors import FrozenMethodInvalidError, UserDeactivatedBanError
from userbot.client import AccountMessagingUnavailableError, UserBotClient, _build_proxy_settings


def write_openrouter_settings(tmp_path):
    """Создаёт минимальный TOML с Telegram credentials и моделями."""
    path = tmp_path / "settings.toml"
    path.write_text(
        '[telegram]\napi_id = 1\napi_hash = "hash"\n\n'
        '[openrouter]\nmodels = ["test/primary", "test/fallback"]\n',
        encoding="utf-8",
    )
    return path


class FakeTelegramClient:
    """Простая подмена Telethon-клиента для unit-тестов."""

    def __init__(self, session_string: object, api_id: int, api_hash: str, proxy: object | None = None) -> None:
        self.session_string = session_string
        self.api_id = api_id
        self.api_hash = api_hash
        self.proxy = proxy
        self.start = AsyncMock()
        self.disconnect = AsyncMock()
        self.run_until_disconnected = AsyncMock()
        self.add_event_handler = Mock()
        self.send_message = AsyncMock()
        self.get_messages = AsyncMock(return_value=[])
        self.get_entity = AsyncMock(return_value="@group")
        self.get_permissions = AsyncMock()
        self.get_me = AsyncMock(return_value=SimpleNamespace(id=111))
        self.invoke = AsyncMock()
        self.joined_targets = []
        self.imported_invites = []
        self.is_connected = lambda: True

    async def __call__(self, request):
        return await self.invoke(request)


def test_extract_event_chat_id_uses_telethon_marked_channel_id():
    """Проверяет совпадение allowlist id с форматом Telegram event.chat_id."""
    from telethon.tl.types import Channel, ChatPhotoEmpty

    import run

    channel = Channel(
        id=123456,
        title="Group",
        photo=ChatPhotoEmpty(),
        date=None,
        megagroup=True,
    )

    assert run._extract_event_chat_id(channel, None) == -(10**12 + 123456)


def test_extract_event_chat_id_normalizes_positive_fallback_from_resolved_entity():
    """Положительный raw ID не вытесняет marked peer ID resolved channel."""
    from telethon.tl.types import Channel, ChatPhotoEmpty

    import run

    channel = Channel(
        id=123456,
        title="Group",
        photo=ChatPhotoEmpty(),
        date=None,
        megagroup=True,
    )

    assert run._extract_event_chat_id(channel, 123456) == -(10**12 + 123456)


def test_extract_resolved_chat_id_uses_marked_channel_id_for_persistence():
    """Scheduled history target-only группы совпадает с Telegram event.chat_id."""
    from telethon.tl.types import Channel, ChatPhotoEmpty

    import run

    channel = Channel(
        id=123456,
        title="Group",
        photo=ChatPhotoEmpty(),
        date=None,
        megagroup=True,
    )

    assert run._extract_resolved_chat_id(channel, None) == -(10**12 + 123456)


def test_private_invite_link_detection_is_case_insensitive():
    """Scheme и host invite URL не влияют на приватную классификацию."""
    import run

    target = "HTTPS://T.ME/+SecretInviteHash"

    assert run._is_invite_link(target) is True
    assert run._redact_group_target(target) == "<private invite link>"


def test_enabled_groups_do_not_fall_back_when_explicit_groups_are_all_disabled():
    """Явно отключённая группа не активируется через legacy compatibility fields."""
    import run

    disabled_group = SimpleNamespace(id="off", enabled=False, group_chat_id=-100123, group_target=None)
    settings = SimpleNamespace(
        groups=[disabled_group],
        enabled_groups=[],
        group_chat_id=-100123,
        group_target=None,
    )

    assert run._enabled_groups_from_settings(settings) == []


@pytest.mark.asyncio
async def test_userbot_client_start_and_stop(monkeypatch):
    """Проверяет, что обёртка делегирует запуск и остановку Telethon-клиенту."""
    fake_client = FakeTelegramClient("session-string", 1, "hash")

    monkeypatch.setattr(
        "userbot.client._build_telegram_client",
        lambda session_string, api_id, api_hash, proxy=None: fake_client,
    )

    client = UserBotClient(session_string="session-string", api_id=1, api_hash="hash")
    await client.start()
    await client.stop()

    fake_client.start.assert_awaited_once()
    fake_client.disconnect.assert_awaited_once()
    assert client.client is fake_client


@pytest.mark.asyncio
async def test_userbot_client_delegates_run_until_disconnected(monkeypatch):
    """Проверяет проксирование run_until_disconnected к Telethon-клиенту."""
    fake_client = FakeTelegramClient("session-string", 1, "hash")
    monkeypatch.setattr(
        "userbot.client._build_telegram_client",
        lambda session_string, api_id, api_hash, proxy=None: fake_client,
    )

    client = UserBotClient(session_string="session-string", api_id=1, api_hash="hash")
    await client.start()
    await client.run_until_disconnected()

    fake_client.run_until_disconnected.assert_awaited_once()


@pytest.mark.asyncio
async def test_userbot_client_checks_global_messaging_without_sending_message(monkeypatch):
    """Health-check использует typing action в Saved Messages и не публикует текст."""
    fake_client = FakeTelegramClient("session-string", 1, "hash")
    monkeypatch.setattr(
        "userbot.client._build_telegram_client",
        lambda session_string, api_id, api_hash, proxy=None: fake_client,
    )

    class Requests:
        class InputPeerSelf:
            pass

        class SendMessageTypingAction:
            pass

        class SetTypingRequest:
            def __init__(self, *, peer, action):
                self.peer = peer
                self.action = action

    monkeypatch.setattr("userbot.client._import_telethon_messaging_requests", lambda: Requests)
    client = UserBotClient(session_string="session-string", api_id=1, api_hash="hash")

    await client.start()
    await client.verify_global_messaging_eligibility()

    request = fake_client.invoke.await_args.args[0]
    assert isinstance(request, Requests.SetTypingRequest)
    assert isinstance(request.peer, Requests.InputPeerSelf)
    assert isinstance(request.action, Requests.SendMessageTypingAction)
    fake_client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_userbot_client_stops_session_when_telegram_rejects_frozen_account(monkeypatch):
    """Глобальная Telegram-блокировка при connect закрывает созданный клиент."""
    fake_client = FakeTelegramClient("session-string", 1, "hash")
    fake_client.start.side_effect = UserDeactivatedBanError(None)
    monkeypatch.setattr(
        "userbot.client._build_telegram_client",
        lambda session_string, api_id, api_hash, proxy=None: fake_client,
    )
    client = UserBotClient(session_string="session-string", api_id=1, api_hash="hash")

    with pytest.raises(AccountMessagingUnavailableError):
        await client.start()

    fake_client.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_userbot_client_quarantines_frozen_method_error_from_messaging_check(monkeypatch):
    """Замороженный аккаунт распознаётся по FROZEN_METHOD_INVALID без публикации текста."""
    fake_client = FakeTelegramClient("session-string", 1, "hash")
    fake_client.invoke.side_effect = FrozenMethodInvalidError(None)
    monkeypatch.setattr(
        "userbot.client._build_telegram_client",
        lambda session_string, api_id, api_hash, proxy=None: fake_client,
    )

    class Requests:
        class InputPeerSelf:
            pass

        class SendMessageTypingAction:
            pass

        class SetTypingRequest:
            def __init__(self, *, peer, action):
                self.peer = peer
                self.action = action

    monkeypatch.setattr("userbot.client._import_telethon_messaging_requests", lambda: Requests)
    client = UserBotClient(session_string="session-string", api_id=1, api_hash="hash")

    await client.start()
    with pytest.raises(AccountMessagingUnavailableError):
        await client.verify_global_messaging_eligibility()


def test_build_proxy_settings_for_http_proxy():
    """Проверяет преобразование HTTP proxy URL в формат Telethon."""
    proxy = _build_proxy_settings("http://user:pass@127.0.0.1:8080")

    assert proxy == {
        "proxy_type": "http",
        "addr": "127.0.0.1",
        "port": 8080,
        "username": "user",
        "password": "pass",
        "rdns": True,
    }


def test_build_proxy_settings_returns_none_when_proxy_missing():
    """Проверяет, что при отсутствии proxy возвращается None."""
    assert _build_proxy_settings(None) is None


def test_build_proxy_settings_rejects_https_proxy():
    """Проверяет явный отказ от неподдерживаемого HTTPS proxy для Telethon."""
    with pytest.raises(ValueError, match="Неподдерживаемая схема proxy"):
        _build_proxy_settings("https://127.0.0.1:8443")


@pytest.mark.asyncio
async def test_build_runtime_context_wires_and_closes_openrouter(monkeypatch, tmp_path):
    """Проверяет единый OpenRouter client и его lifecycle в RuntimeContext."""
    import run

    captured = {}
    fake_ai_client = SimpleNamespace(close=AsyncMock())
    write_catalog = AsyncMock(
        return_value={
            "status": "ok",
            "models_count": 2,
            "output_path": "logs/openrouter_free_models.json",
        }
    )

    def build_ai_client(**kwargs):
        captured.update(kwargs)
        return fake_ai_client

    monkeypatch.setattr(run, "OpenRouterClient", build_ai_client)
    monkeypatch.setattr(run, "write_free_models_catalog", write_catalog, raising=False)
    settings = SimpleNamespace(
        db_path=":memory:",
        prompts_dir="ai/prompts",
        topics_path="ai/prompts/topics.md",
        bot_profiles_dir="ai/prompts/bots",
        openrouter_api_key=SecretStr("test-key"),
        openrouter_models=["test/primary", "test/fallback"],
        openrouter_temperature=None,
        openrouter_request_timeout_seconds=45.0,
        openrouter_retry_initial_interval_ms=500,
        openrouter_retry_max_interval_ms=5000,
        openrouter_retry_max_elapsed_time_ms=15000,
        openrouter_retry_jitter_ms=300,
        proxy=SecretStr("http://user:pass@127.0.0.1:8080"),
        swarm_max_output_chars=400,
        swarm_max_mentions_per_message=2,
        swarm_history_retention_days=30,
    )

    runtime = await run._build_runtime_context(settings)

    write_catalog.assert_awaited_once_with(
        api_key="test-key",
        output_path="logs/openrouter_free_models.json",
        proxy="http://user:pass@127.0.0.1:8080",
        timeout_seconds=45.0,
    )
    assert runtime.ai_client is fake_ai_client
    assert captured == {
        "api_key": "test-key",
        "models": ["test/primary", "test/fallback"],
        "temperature": None,
        "proxy": "http://user:pass@127.0.0.1:8080",
        "request_timeout_seconds": 45.0,
        "retry_initial_interval_ms": 500,
        "retry_max_interval_ms": 5000,
        "retry_max_elapsed_time_ms": 15000,
        "retry_jitter_ms": 300,
        "max_output_chars": 400,
        "max_mentions_per_message": 2,
    }
    await runtime.close()
    fake_ai_client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_runtime_context_preserves_init_error_and_closes_all_resources(monkeypatch):
    """Проверяет cleanup после создания AI client без потери исходной ошибки."""
    import run

    database = SimpleNamespace(open=AsyncMock(), close=AsyncMock())
    history = SimpleNamespace(init_db=AsyncMock(), prune_older_than=AsyncMock())
    ai_client = SimpleNamespace(close=AsyncMock(side_effect=RuntimeError("close failed")))
    topic_selector = SimpleNamespace(load=AsyncMock(side_effect=RuntimeError("topics failed")))
    monkeypatch.setattr(run, "SQLiteDatabase", lambda _path: database)
    monkeypatch.setattr(run, "MessageHistory", lambda _database: history)
    monkeypatch.setattr(
        run,
        "PromptLoader",
        lambda _path: SimpleNamespace(load_important_service_scenarios=AsyncMock(return_value=())),
    )
    monkeypatch.setattr(run, "OpenRouterClient", lambda **_kwargs: ai_client)
    monkeypatch.setattr(run, "TopicSelector", lambda _path: topic_selector)
    settings = SimpleNamespace(
        db_path=":memory:",
        prompts_dir="prompts",
        topics_path="topics.md",
        openrouter_api_key="key",
        openrouter_models=["one", "two"],
        openrouter_temperature=None,
        openrouter_request_timeout_seconds=45.0,
        openrouter_retry_initial_interval_ms=500,
        openrouter_retry_max_interval_ms=5000,
        openrouter_retry_max_elapsed_time_ms=15000,
        openrouter_retry_jitter_ms=300,
        proxy=None,
        swarm_max_output_chars=400,
        swarm_max_mentions_per_message=2,
    )

    with pytest.raises(RuntimeError, match="topics failed"):
        await run._build_runtime_context(settings)

    ai_client.close.assert_awaited_once()
    database.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_runs_swarm_mode(monkeypatch, tmp_path):
    """Проверяет, что main() запускает swarm-bootstrap и закрывает runtime."""
    import run

    settings = Settings(
        openrouter_api_key="openrouter-key",
        db_path=":memory:",
        settings_path=str(write_openrouter_settings(tmp_path)),
    )
    settings.mode = "swarm"
    runtime_context = SimpleNamespace(close=AsyncMock())
    scheduler = SimpleNamespace(start=Mock(), add_job=Mock(), shutdown=Mock())

    monkeypatch.setattr(run, "load_settings_or_exit", lambda: settings)
    monkeypatch.setattr(run, "_build_runtime_context", AsyncMock(return_value=runtime_context))
    monkeypatch.setattr(run, "AsyncIOScheduler", lambda: scheduler)
    monkeypatch.setattr(run, "_run_swarm_mode", AsyncMock())

    await run.main()

    scheduler.start.assert_called_once()
    run._run_swarm_mode.assert_awaited_once_with(settings, runtime_context, scheduler)
    runtime_context.close.assert_awaited_once()


def test_run_cli_treats_keyboard_interrupt_as_graceful_shutdown(monkeypatch):
    """Ctrl+C после async cleanup не печатает traceback из launcher."""
    import run

    main_result = object()
    monkeypatch.setattr(run, "main", Mock(return_value=main_result))
    asyncio_run = Mock(side_effect=KeyboardInterrupt)
    monkeypatch.setattr(run.asyncio, "run", asyncio_run)

    run._run_cli()

    asyncio_run.assert_called_once_with(main_result)


def test_run_cli_propagates_runtime_errors(monkeypatch):
    """Launcher не маскирует ошибки приложения, не связанные с Ctrl+C."""
    import run

    main_result = object()
    monkeypatch.setattr(run, "main", Mock(return_value=main_result))
    monkeypatch.setattr(run.asyncio, "run", Mock(side_effect=RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        run._run_cli()


@pytest.mark.asyncio
async def test_register_swarm_handlers_registers_handler_per_bot(monkeypatch):
    """Проверяет регистрацию addressed handlers для каждого активного бота."""
    import run

    fake_client_anna = FakeTelegramClient("anna", 1, "hash")
    fake_client_mike = FakeTelegramClient("mike", 1, "hash")
    manager = SimpleNamespace(
        active_bot_ids=["anna", "mike"],
        bot_profiles=[
            SimpleNamespace(id="anna", enabled=True, telegram_user_id=101, persona_file="anna.md"),
            SimpleNamespace(id="mike", enabled=True, telegram_user_id=202, persona_file="mike.md"),
        ],
        get_client=lambda bot_id: SimpleNamespace(client=fake_client_anna if bot_id == "anna" else fake_client_mike),
        swarm_user_ids={101, 202},
        human_slot=lambda _bot_id: _AsyncNullContext(),
    )
    runtime = SimpleNamespace(history=object(), prompt_composer=object(), ai_client=object())
    monkeypatch.setitem(__import__("sys").modules, "telethon", SimpleNamespace(events=SimpleNamespace(NewMessage=lambda: "new-message")))

    await run._register_swarm_handlers(manager, runtime, lambda: SimpleNamespace())

    assert fake_client_anna.add_event_handler.call_count == 1
    assert fake_client_mike.add_event_handler.call_count == 1


@pytest.mark.asyncio
async def test_register_swarm_handlers_skips_profiles_outside_active_pool(monkeypatch):
    """Проверяет, что handler не регистрируется для бота, исключённого при startup."""
    import run

    fake_client_anna = FakeTelegramClient("anna", 1, "hash")
    manager = SimpleNamespace(
        active_bot_ids=["anna"],
        bot_profiles=[
            SimpleNamespace(id="anna", enabled=True, telegram_user_id=101, persona_file="anna.md"),
            SimpleNamespace(id="vitaly", enabled=True, telegram_user_id=None, persona_file="vitaly.md"),
        ],
        get_client=lambda bot_id: SimpleNamespace(client=fake_client_anna) if bot_id == "anna" else (_ for _ in ()).throw(KeyError(bot_id)),
        swarm_user_ids={101},
        human_slot=lambda _bot_id: _AsyncNullContext(),
    )
    runtime = SimpleNamespace(history=object(), prompt_composer=object(), ai_client=object())
    monkeypatch.setitem(__import__("sys").modules, "telethon", SimpleNamespace(events=SimpleNamespace(NewMessage=lambda: "new-message")))

    await run._register_swarm_handlers(manager, runtime, lambda: SimpleNamespace())

    assert fake_client_anna.add_event_handler.call_count == 1


@pytest.mark.asyncio
async def test_run_swarm_mode_starts_manager_registers_scheduler_and_supervises(monkeypatch, tmp_path):
    """Интеграционно проверяет запуск swarm-режима с несколькими ботами."""
    import run

    settings = Settings(
        openrouter_api_key="openrouter-key",
        group_target="@group",
        db_path=":memory:",
        settings_path=str(write_openrouter_settings(tmp_path)),
    )
    settings.mode = "swarm"
    settings.proxy = SecretStr("http://user:pass@127.0.0.1:8080")
    settings.swarm_tick_seconds = 60
    settings.swarm_bots = [
        SimpleNamespace(id="anna", session_string="anna-session", persona_file="anna.md", enabled=True, temperature=0.9, session_env="SESSION_STRING_ANNA"),
        SimpleNamespace(id="mike", session_string="mike-session", persona_file="mike.md", enabled=True, temperature=0.8, session_env="SESSION_STRING_MIKE"),
    ]

    fake_anna_client = FakeTelegramClient("anna", 1, "hash")
    fake_mike_client = FakeTelegramClient("mike", 1, "hash")
    manager = SimpleNamespace(
        active_bot_ids=["anna", "mike"],
        bot_profiles=[
            SimpleNamespace(id="anna", enabled=True, telegram_user_id=101, persona_file="anna.md"),
            SimpleNamespace(id="mike", enabled=True, telegram_user_id=202, persona_file="mike.md"),
        ],
        start=AsyncMock(),
        stop=AsyncMock(),
        supervise_bot=AsyncMock(side_effect=[None, None]),
        get_client=lambda bot_id: SimpleNamespace(client=fake_anna_client if bot_id == "anna" else fake_mike_client),
        swarm_user_ids={101, 202},
    )
    runtime = SimpleNamespace(
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        ai_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=SimpleNamespace(backfill_legacy_group_scope=AsyncMock()),
    )
    scheduler = SimpleNamespace(add_job=Mock())

    manager_kwargs = {}

    def build_manager(**kwargs):
        manager_kwargs.update(kwargs)
        return manager

    monkeypatch.setattr(run, "SwarmManager", build_manager)
    monkeypatch.setattr(run, "_register_swarm_handlers", AsyncMock())
    monkeypatch.setattr(run, "_log_resolved_group", AsyncMock())
    resolved_group = SimpleNamespace(id=123456, username="group")
    monkeypatch.setattr(run, "_resolve_group_target", AsyncMock(return_value=resolved_group))
    monkeypatch.setattr(run, "_extract_event_chat_id", lambda _target, _fallback: -100123456)
    monkeypatch.setattr(run, "SwarmOrchestrator", lambda **kwargs: SimpleNamespace(run_once=AsyncMock()))

    await run._run_swarm_mode(settings, runtime, scheduler)

    constructed_client = manager_kwargs["client_factory"](settings.swarm_bots[0])

    manager.start.assert_awaited_once()
    assert constructed_client.proxy == "http://user:pass@127.0.0.1:8080"
    run._register_swarm_handlers.assert_awaited_once_with(
        manager,
        runtime,
        run._register_swarm_handlers.await_args.args[2],
        {-100123456},
    )
    scheduler.add_job.assert_called_once()
    assert scheduler.add_job.call_args.kwargs["seconds"] == 60
    runtime.exchange_store.backfill_legacy_group_scope.assert_awaited_once_with(
        group_id="legacy",
        group_chat_id=-100123456,
    )
    manager.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_swarm_mode_reuses_group_orchestrator_between_ticks(monkeypatch, tmp_path):
    """Проверяет, что scheduler tick переиспользует orchestrator для неизменной группы."""
    import run

    settings = Settings(
        openrouter_api_key="openrouter-key",
        group_chat_id=-100111,
        group_target="@group",
        db_path=":memory:",
        settings_path=str(write_openrouter_settings(tmp_path)),
    )
    settings.mode = "swarm"
    settings.swarm_tick_seconds = 30
    settings.swarm_bots = [
        SimpleNamespace(id="anna", session_string="anna-session", persona_file="anna.md", enabled=True, temperature=0.9, session_env="SESSION_STRING_ANNA"),
        SimpleNamespace(id="mike", session_string="mike-session", persona_file="mike.md", enabled=True, temperature=0.8, session_env="SESSION_STRING_MIKE"),
    ]

    manager = SimpleNamespace(
        active_bot_ids=["anna", "mike"],
        bot_profiles=[
            SimpleNamespace(id="anna", enabled=True, telegram_user_id=101, persona_file="anna.md"),
            SimpleNamespace(id="mike", enabled=True, telegram_user_id=202, persona_file="mike.md"),
        ],
        start=AsyncMock(),
        stop=AsyncMock(),
        supervise_bot=AsyncMock(side_effect=[None, None]),
        get_client=lambda _bot_id: SimpleNamespace(client=FakeTelegramClient("anna", 1, "hash")),
        swarm_user_ids={101, 202},
    )
    runtime = SimpleNamespace(
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        ai_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=SimpleNamespace(),
    )
    scheduler = SimpleNamespace(add_job=Mock())
    created_orchestrators = []

    class FakeOrchestrator:
        """Orchestrator-заглушка для подсчёта созданных экземпляров."""

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.run_once = AsyncMock(return_value=False)
            created_orchestrators.append(self)

    monkeypatch.setattr(run, "SwarmManager", lambda **kwargs: manager)
    monkeypatch.setattr(run, "_register_swarm_handlers", AsyncMock())
    monkeypatch.setattr(run, "_log_resolved_group", AsyncMock())
    monkeypatch.setattr(run, "_resolve_group_target", AsyncMock(return_value=SimpleNamespace(id=-100111, username="group")))
    monkeypatch.setattr(run, "SwarmOrchestrator", FakeOrchestrator)

    await run._run_swarm_mode(settings, runtime, scheduler)
    tick = scheduler.add_job.call_args.args[0]

    await tick()
    await tick()

    assert len(created_orchestrators) == 1
    assert created_orchestrators[0].run_once.await_count == 2


async def _build_swarm_tick_with_distinct_clients(monkeypatch, tmp_path):
    """Собирает scheduler tick с различимыми Telegram-клиентами для runtime-тестов."""
    import run

    settings = Settings(
        openrouter_api_key="openrouter-key",
        group_chat_id=-100111,
        group_target="@group",
        db_path=":memory:",
        settings_path=str(write_openrouter_settings(tmp_path)),
    )
    settings.mode = "swarm"
    settings.swarm_bots = [
        SimpleNamespace(id="anna", session_string="anna-session", persona_file="anna.md", enabled=True, temperature=0.9, session_env="SESSION_STRING_ANNA"),
        SimpleNamespace(id="mike", session_string="mike-session", persona_file="mike.md", enabled=True, temperature=0.8, session_env="SESSION_STRING_MIKE"),
    ]
    clients = {
        "anna": FakeTelegramClient("anna", 1, "hash"),
        "mike": FakeTelegramClient("mike", 2, "hash"),
    }
    manager = SimpleNamespace(
        active_bot_ids=["anna", "mike"],
        bot_profiles=[
            SimpleNamespace(id="anna", enabled=True, telegram_user_id=101, persona_file="anna.md"),
            SimpleNamespace(id="mike", enabled=True, telegram_user_id=202, persona_file="mike.md"),
        ],
        start=AsyncMock(),
        stop=AsyncMock(),
        supervise_bot=AsyncMock(side_effect=[None, None]),
        get_client=lambda bot_id: SimpleNamespace(client=clients[bot_id]),
        swarm_user_ids={101, 202},
    )
    runtime = SimpleNamespace(
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        ai_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=SimpleNamespace(),
    )
    scheduler = SimpleNamespace(add_job=Mock())
    resolve_group_target = AsyncMock(return_value=SimpleNamespace(id=-100111, username="group"))

    monkeypatch.setattr(run, "SwarmManager", lambda **kwargs: manager)
    monkeypatch.setattr(run, "_register_swarm_handlers", AsyncMock())
    monkeypatch.setattr(run, "_log_resolved_group", AsyncMock())
    monkeypatch.setattr(run, "_resolve_group_target", resolve_group_target)
    monkeypatch.setattr(run, "SwarmOrchestrator", lambda **kwargs: SimpleNamespace(run_once=AsyncMock(return_value=False)))

    await run._run_swarm_mode(settings, runtime, scheduler)
    resolve_group_target.reset_mock()
    tick = scheduler.add_job.call_args.args[0]
    tick.test_runtime = runtime
    return tick, manager, clients, resolve_group_target


@pytest.mark.asyncio
async def test_scheduler_tick_resolves_groups_through_current_active_client(monkeypatch, tmp_path):
    """Tick не использует остановленный стартовый клиент после runtime-disable."""
    tick, manager, clients, resolve_group_target = await _build_swarm_tick_with_distinct_clients(monkeypatch, tmp_path)
    manager.active_bot_ids[:] = ["mike"]

    await tick()

    assert resolve_group_target.await_args.args[0] is clients["mike"]


@pytest.mark.asyncio
async def test_scheduler_tick_skips_group_resolution_without_active_clients(monkeypatch, tmp_path):
    """Tick безопасно пропускается при временно пустом active pool."""
    tick, manager, _clients, resolve_group_target = await _build_swarm_tick_with_distinct_clients(monkeypatch, tmp_path)
    manager.active_bot_ids.clear()

    assert await tick() is False
    resolve_group_target.assert_not_awaited()


@pytest.mark.asyncio
async def test_settings_reload_updates_shared_ai_safety_limits(monkeypatch, tmp_path):
    """Reload применяет изменяемые safety limits к общему AI-клиенту."""
    import copy
    import run

    class ReloadWatcher:
        def __init__(self, settings):
            reloaded = copy.copy(settings)
            reloaded.swarm_max_output_chars = 777
            reloaded.swarm_max_mentions_per_message = 1
            self.poll = Mock(side_effect=[reloaded, None])

    monkeypatch.setattr(run, "SettingsReloadWatcher", ReloadWatcher)
    tick, _manager, _clients, _resolve = await _build_swarm_tick_with_distinct_clients(
        monkeypatch, tmp_path
    )

    await tick()

    assert tick.test_runtime.ai_client.max_output_chars == 777
    assert tick.test_runtime.ai_client.max_mentions_per_message == 1


@pytest.mark.asyncio
async def test_scheduler_retries_pending_reload_group_without_new_file_change(monkeypatch, tmp_path):
    """Временно недоступная reload-группа повторно проверяется на следующем tick."""
    import copy
    import run

    new_group = SimpleNamespace(
        id="new",
        city="New",
        enabled=True,
        group_chat_id=-100222,
        group_target="@new",
        active_windows_utc=[],
        initiator_offset_minutes=(0, 0),
        responder_delay_minutes=(0, 0),
        max_turns_per_exchange=2,
    )

    class ReloadWatcher:
        def __init__(self, settings):
            reloaded = copy.copy(settings)
            old_group = run._enabled_groups_from_settings(settings)[0]
            reloaded.groups = [old_group, new_group]
            reloaded.enabled_groups = [old_group, new_group]
            self.poll = Mock(side_effect=[reloaded, None])

    filter_groups = AsyncMock()

    async def filter_side_effect(_manager, previous, candidates):
        return [candidates[0]] if filter_groups.await_count == 1 else candidates

    filter_groups.side_effect = filter_side_effect
    monkeypatch.setattr(run, "SettingsReloadWatcher", ReloadWatcher)
    monkeypatch.setattr(run, "_filter_reload_ready_groups", filter_groups)
    tick, _manager, _clients, _resolve = await _build_swarm_tick_with_distinct_clients(
        monkeypatch, tmp_path
    )

    await tick()
    await tick()

    assert filter_groups.await_count == 2
    assert [group.id for group in filter_groups.await_args_list[1].args[2]] == ["legacy", "new"]


def test_group_orchestrator_cache_rebuilds_on_signature_change_and_prunes():
    """Проверяет пересоздание cache entry при смене подписи и очистку отключённых групп."""
    import run

    cache = {}
    created = []

    first = run._get_cached_group_orchestrator(
        cache,
        "batumi",
        ("batumi", "Batumi", "10-12"),
        lambda: created.append("first") or object(),
    )
    reused = run._get_cached_group_orchestrator(
        cache,
        "batumi",
        ("batumi", "Batumi", "10-12"),
        lambda: created.append("unexpected") or object(),
    )
    rebuilt = run._get_cached_group_orchestrator(
        cache,
        "batumi",
        ("batumi", "Batumi", "12-14"),
        lambda: created.append("rebuilt") or object(),
    )
    run._get_cached_group_orchestrator(
        cache,
        "tbilisi",
        ("tbilisi", "Tbilisi", "10-12"),
        lambda: created.append("tbilisi") or object(),
    )

    assert first is reused
    assert rebuilt is not first
    assert created == ["first", "rebuilt", "tbilisi"]

    run._prune_orchestrator_cache(cache, {"tbilisi"})

    assert set(cache) == {"tbilisi"}


def test_rotate_groups_for_tick_advances_start_without_parallelism():
    """Проверяет циклическую смену первой группы при сохранении последовательности."""
    import run

    groups = [
        SimpleNamespace(id="batumi"),
        SimpleNamespace(id="tbilisi"),
        SimpleNamespace(id="kutaisi"),
    ]

    first, next_index = run._rotate_groups_for_tick(groups, 0)
    second, next_index = run._rotate_groups_for_tick(groups, next_index)
    third, next_index = run._rotate_groups_for_tick(groups, next_index)

    assert [[group.id for group in tick] for tick in (first, second, third)] == [
        ["batumi", "tbilisi", "kutaisi"],
        ["tbilisi", "kutaisi", "batumi"],
        ["kutaisi", "batumi", "tbilisi"],
    ]
    assert next_index == 0


def test_rotate_groups_for_tick_normalizes_index_after_reload():
    """Проверяет нормализацию позиции после уменьшения списка групп."""
    import run

    groups = [SimpleNamespace(id="batumi"), SimpleNamespace(id="tbilisi")]

    ordered, next_index = run._rotate_groups_for_tick(groups, 5)
    empty, empty_next_index = run._rotate_groups_for_tick([], next_index)

    assert [group.id for group in ordered] == ["tbilisi", "batumi"]
    assert next_index == 0
    assert empty == []
    assert empty_next_index == 0


def test_group_orchestrator_signature_changes_with_scheduled_llm_gate():
    """Отключение scheduled LLM инвалидирует кешированный orchestrator."""
    import run

    group = SimpleNamespace(
        id="danang",
        city="Da Nang",
        group_chat_id=-100123,
        group_target="@danang",
        active_windows_utc=["10-11"],
        initiator_offset_minutes=(0, 30),
        responder_delay_minutes=(3, 10),
        max_turns_per_exchange=2,
    )
    common = {
        "group": group,
        "group_target": "@danang",
        "group_chat_id": -100123,
        "skip_if_recent_human_activity": True,
    }

    enabled = run._build_group_orchestrator_signature(
        **common,
        allow_external_llm_for_scheduled=True,
    )
    disabled = run._build_group_orchestrator_signature(
        **common,
        allow_external_llm_for_scheduled=False,
    )

    assert enabled != disabled


@pytest.mark.asyncio
async def test_run_swarm_mode_requires_two_active_bots_after_start(monkeypatch, tmp_path):
    """Проверяет отказ запуска, если после startup остался один бот."""
    import run

    settings = Settings(
        openrouter_api_key="openrouter-key",
        group_target="@group",
        db_path=":memory:",
        settings_path=str(write_openrouter_settings(tmp_path)),
    )
    settings.mode = "swarm"
    settings.swarm_bots = [
        SimpleNamespace(id="anna", session_string="anna-session", persona_file="anna.md", enabled=True, temperature=0.9, session_env="SESSION_STRING_ANNA"),
        SimpleNamespace(id="mike", session_string="mike-session", persona_file="mike.md", enabled=True, temperature=0.8, session_env="SESSION_STRING_MIKE"),
    ]
    manager = SimpleNamespace(
        active_bot_ids=["anna"],
        bot_profiles=[SimpleNamespace(id="anna", enabled=True, telegram_user_id=101, persona_file="anna.md")],
        start=AsyncMock(),
        stop=AsyncMock(),
        supervise_bot=AsyncMock(),
        get_client=lambda _bot_id: SimpleNamespace(client=FakeTelegramClient("anna", 1, "hash")),
        swarm_user_ids={101},
    )
    runtime = SimpleNamespace(
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        ai_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=SimpleNamespace(),
    )
    scheduler = SimpleNamespace(add_job=Mock())

    monkeypatch.setattr(run, "SwarmManager", lambda **kwargs: manager)

    with pytest.raises(ValueError, match="at least two active bots"):
        await run._run_swarm_mode(settings, runtime, scheduler)

    manager.start.assert_awaited_once()
    scheduler.add_job.assert_not_called()


@pytest.mark.asyncio
async def test_run_swarm_mode_rechecks_durably_quarantined_bot_at_startup(monkeypatch, tmp_path):
    """Долговременная quarantine проверяется на старте, но не блокирует автозапуск."""
    import run

    settings = Settings(
        openrouter_api_key="openrouter-key",
        group_target="@group",
        db_path=":memory:",
        settings_path=str(write_openrouter_settings(tmp_path)),
    )
    settings.mode = "swarm"
    settings.swarm_bots = [
        SimpleNamespace(id="anna", session_string="anna-session", persona_file="anna.md", enabled=True, temperature=0.9, session_env="SESSION_STRING_ANNA"),
        SimpleNamespace(id="mike", session_string="mike-session", persona_file="mike.md", enabled=True, temperature=0.8, session_env="SESSION_STRING_MIKE"),
    ]
    runtime = SimpleNamespace(
        exchange_store=SimpleNamespace(
            reset_startup_availability=AsyncMock(),
        )
    )
    scheduler = SimpleNamespace(add_job=Mock())
    manager = SimpleNamespace(start=AsyncMock(), stop=AsyncMock(), active_bot_ids=["anna", "mike"], get_client=lambda _: SimpleNamespace(client=FakeTelegramClient("anna", 1, "hash")), swarm_user_ids=set(), supervise_bot=AsyncMock())
    monkeypatch.setattr(run, "SwarmManager", lambda **_: manager)
    monkeypatch.setattr(run, "_register_swarm_handlers", AsyncMock())
    monkeypatch.setattr(run, "_resolve_group_target", AsyncMock(return_value=SimpleNamespace(id=1)))
    monkeypatch.setattr(run, "_log_resolved_group", AsyncMock())

    await run._run_swarm_mode(settings, runtime, scheduler)

    runtime.exchange_store.reset_startup_availability.assert_awaited_once()
    manager.start.assert_awaited_once()
    manager.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_group_membership_joins_public_target(monkeypatch):
    """Проверяет автovступление в публичную группу через group_target."""
    import run

    telegram_client = FakeTelegramClient("anna", 1, "hash")
    telegram_client.get_entity = AsyncMock(return_value="@joined")

    async def join_public_group(target: str):
        telegram_client.joined_targets.append(target)
        return "@joined"

    join_group = AsyncMock(side_effect=join_public_group)
    wrapper = SimpleNamespace(client=telegram_client, join_group=join_group, join_invite_link=AsyncMock())

    resolved = await run._ensure_group_membership(wrapper, None, "@my_group", "anna")

    assert resolved == "@joined"
    join_group.assert_awaited_once_with("@my_group")


@pytest.mark.asyncio
async def test_ensure_group_membership_joins_public_link_even_if_entity_resolves_without_membership():
    """Проверяет, что публичный entity-резолв не маскирует отсутствие членства."""
    import run

    class DialogClient(FakeTelegramClient):
        async def iter_dialogs(self):
            if False:
                yield None

    telegram_client = DialogClient("anna", 1, "hash")
    telegram_client.get_entity = AsyncMock(side_effect=["@public_group", "@joined_after_join"])

    async def join_public_group(target: str):
        telegram_client.joined_targets.append(target)
        return "@joined_after_join"

    join_group = AsyncMock(side_effect=join_public_group)
    wrapper = SimpleNamespace(client=telegram_client, join_group=join_group, join_invite_link=AsyncMock())

    resolved = await run._ensure_group_membership(
        wrapper,
        None,
        "https://t.me/public_group",
        "anna",
    )

    assert resolved == "@joined_after_join"
    join_group.assert_awaited_once_with("@public_group")


@pytest.mark.asyncio
async def test_ensure_group_membership_imports_invite_link(monkeypatch):
    """Проверяет автovступление в приватную группу через invite link."""
    import run

    telegram_client = FakeTelegramClient("anna", 1, "hash")
    telegram_client.get_entity = AsyncMock(return_value="@joined")

    async def import_invite(link: str):
        telegram_client.imported_invites.append(link)
        return "@joined"

    join_invite_link = AsyncMock(side_effect=import_invite)
    wrapper = SimpleNamespace(client=telegram_client, join_group=AsyncMock(), join_invite_link=join_invite_link)

    resolved = await run._ensure_group_membership(wrapper, None, "https://t.me/+InviteHash", "anna")

    assert resolved == "@joined"
    join_invite_link.assert_awaited_once_with("https://t.me/+InviteHash")


@pytest.mark.asyncio
async def test_resolve_group_target_skips_get_entity_for_invite_link():
    """Проверяет, что invite link не используется для прямого get_entity-резолва."""
    import run

    class DialogClient(FakeTelegramClient):
        async def iter_dialogs(self):
            if False:
                yield None

    telegram_client = DialogClient("anna", 1, "hash")

    resolved = await run._resolve_group_target(telegram_client, 123, "https://t.me/+InviteHash")

    assert resolved is None
    telegram_client.get_entity.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_group_target_redacts_private_invite_link_in_logs(caplog):
    """Проверяет, что приватная invite-ссылка не попадает в логи целиком."""
    import logging
    import run

    class DialogClient(FakeTelegramClient):
        async def iter_dialogs(self):
            if False:
                yield None

    telegram_client = DialogClient("anna", 1, "hash")

    with caplog.at_level(logging.INFO):
        resolved = await run._resolve_group_target(telegram_client, 123, "https://t.me/+SecretInviteHash")

    assert resolved is None
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "SecretInviteHash" not in messages
    assert "<private invite link>" in messages


@pytest.mark.asyncio
async def test_ensure_group_membership_raises_clear_error_when_group_id_is_unavailable():
    """Проверяет понятную ошибку, если бот не видит группу по корректному chat_id."""
    import run

    class DialogClient(FakeTelegramClient):
        async def iter_dialogs(self):
            if False:
                yield None

    telegram_client = DialogClient("anna", 1, "hash")
    wrapper = SimpleNamespace(client=telegram_client, join_group=AsyncMock(), join_invite_link=AsyncMock())

    with pytest.raises(ValueError, match="не имеет доступа к группе с GROUP_CHAT_ID=123"):
        await run._ensure_group_membership(wrapper, 123, "https://t.me/+InviteHash", "anna")

    wrapper.join_invite_link.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_group_membership_returns_dialog_entity_without_join():
    """Проверяет, что при уже доступной группе дополнительный join не нужен."""
    import run

    entity = SimpleNamespace(id=123)

    class DialogClient(FakeTelegramClient):
        async def iter_dialogs(self):
            yield SimpleNamespace(id=123, entity=entity)

    telegram_client = DialogClient("anna", 1, "hash")
    wrapper = SimpleNamespace(client=telegram_client, join_group=AsyncMock(), join_invite_link=AsyncMock())

    resolved = await run._ensure_group_membership(wrapper, 123, None, "anna")

    assert resolved is entity
    wrapper.join_group.assert_not_called()
    wrapper.join_invite_link.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_group_membership_skips_join_when_public_dialog_is_already_present():
    """Проверяет, что для уже доступной публичной группы дополнительный join не нужен."""
    import run

    entity = SimpleNamespace(id=555, username="public_group")

    class DialogClient(FakeTelegramClient):
        async def iter_dialogs(self):
            yield SimpleNamespace(id=555, entity=entity)

    telegram_client = DialogClient("anna", 1, "hash")
    wrapper = SimpleNamespace(client=telegram_client, join_group=AsyncMock(), join_invite_link=AsyncMock())

    resolved = await run._ensure_group_membership(
        wrapper,
        None,
        "https://t.me/public_group",
        "anna",
    )

    assert resolved is entity
    wrapper.join_group.assert_not_called()
    wrapper.join_invite_link.assert_not_called()


@pytest.mark.asyncio
async def test_multi_group_membership_scans_dialogs_once_for_all_groups(monkeypatch):
    """Проверяет единый индекс dialog для всех membership-проверок userbot."""
    import run

    first_entity = SimpleNamespace(id=101, username="first")
    second_entity = SimpleNamespace(id=202, username="second")

    class DialogClient(FakeTelegramClient):
        def __init__(self):
            super().__init__("anna", 1, "hash")
            self.iter_dialogs_calls = 0

        async def iter_dialogs(self):
            self.iter_dialogs_calls += 1
            yield SimpleNamespace(id=101, entity=first_entity)
            yield SimpleNamespace(id=202, entity=second_entity)

    telegram_client = DialogClient()
    wrapper = SimpleNamespace(client=telegram_client, join_group=AsyncMock(), join_invite_link=AsyncMock())
    monkeypatch.setattr(run.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(run, "_pick_startup_membership_delay_seconds", lambda: 30.0)
    hook = run._build_multi_group_membership_startup_hook(
        groups=[
            SimpleNamespace(id="first", enabled=True, group_chat_id=101, group_target="@first"),
            SimpleNamespace(id="second", enabled=True, group_chat_id=202, group_target="@second"),
        ],
    )

    wrapper.verify_global_messaging_eligibility = AsyncMock()
    resolved = await hook(SimpleNamespace(id="anna"), wrapper)

    assert resolved == {"first": first_entity, "second": second_entity}
    assert await run._resolve_group_target(telegram_client, 101, "@first") is first_entity
    assert await run._resolve_group_target(telegram_client, 202, "@second") is second_entity
    assert telegram_client.iter_dialogs_calls == 1
    wrapper.join_group.assert_not_awaited()


@pytest.mark.asyncio
async def test_multi_group_membership_hook_reads_current_groups_on_reconnect(monkeypatch):
    """Reconnect health-check использует актуальный registry групп после reload."""
    import run

    groups = [SimpleNamespace(id="old", enabled=True, group_chat_id=101, group_target="@old")]
    wrapper = SimpleNamespace(
        client=FakeTelegramClient("anna", 1, "hash"),
        verify_global_messaging_eligibility=AsyncMock(),
    )
    monkeypatch.setattr(run.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(run, "_build_group_dialog_index", AsyncMock(return_value={}))
    require_group = AsyncMock(return_value=SimpleNamespace(id=202))
    monkeypatch.setattr(run, "_require_group_availability", require_group)
    hook = run._build_multi_group_membership_startup_hook(groups=lambda: groups)
    groups[:] = [SimpleNamespace(id="new", enabled=True, group_chat_id=202, group_target="@new")]

    resolved = await hook(SimpleNamespace(id="anna"), wrapper)

    assert set(resolved) == {"new"}
    assert require_group.await_args.args[1].id == "new"


@pytest.mark.asyncio
async def test_multi_group_membership_logs_bot_write_permission(monkeypatch, caplog):
    """Проверяет стартовый лог возможности бота писать в группу."""
    import logging
    import run

    telegram_client = FakeTelegramClient("anna", 1, "hash")
    telegram_client.get_permissions = AsyncMock(
        side_effect=[
            SimpleNamespace(
                is_admin=False,
                participant=SimpleNamespace(banned_rights=SimpleNamespace(send_messages=True)),
            ),
            SimpleNamespace(send_messages=False),
        ]
    )
    wrapper = SimpleNamespace(client=telegram_client, verify_global_messaging_eligibility=AsyncMock())
    monkeypatch.setattr(run.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(run, "_pick_startup_membership_delay_seconds", lambda: 30.0)
    monkeypatch.setattr(run, "_ensure_group_membership", AsyncMock(return_value=SimpleNamespace(id=101)))

    hook = run._build_multi_group_membership_startup_hook(
        groups=[SimpleNamespace(id="first", enabled=True, group_chat_id=101, group_target="@first")],
    )

    with caplog.at_level(logging.INFO), pytest.raises(run.GroupAvailabilityError, match="group_write_unavailable:first"):
        await hook(SimpleNamespace(id="anna"), wrapper)

    assert any(
        "bot_id=anna group_id=first can_write=False "
        "participant_banned_rights.send_messages=True "
        "default_banned_rights.send_messages=False is_admin=False" in record.getMessage()
        for record in caplog.records
    )
    assert any("попал в block по группе group_id=first" in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_multi_group_membership_rejects_unknown_write_permission(monkeypatch, caplog):
    """Проверяет, что неизвестное право записи отклоняет group-level startup."""
    import logging
    import run

    telegram_client = FakeTelegramClient("anna", 1, "hash")
    telegram_client.get_permissions = AsyncMock(side_effect=RuntimeError("permissions unavailable"))
    wrapper = SimpleNamespace(client=telegram_client, verify_global_messaging_eligibility=AsyncMock())
    monkeypatch.setattr(run.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(run, "_pick_startup_membership_delay_seconds", lambda: 30.0)
    monkeypatch.setattr(run, "_ensure_group_membership", AsyncMock(return_value=SimpleNamespace(id=101)))

    hook = run._build_multi_group_membership_startup_hook(
        groups=[SimpleNamespace(id="first", enabled=True, group_chat_id=101, group_target="@first")],
    )

    with caplog.at_level(logging.WARNING), pytest.raises(run.GroupAvailabilityError, match="group_write_unavailable:first"):
        await hook(SimpleNamespace(id="anna"), wrapper)
    assert any("bot_id=anna group_id=first can_write=unknown" in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_multi_group_membership_rejects_unresolved_enabled_group(monkeypatch):
    """Unresolved enabled-группа делает startup аккаунта неуспешным."""
    import run

    wrapper = SimpleNamespace(
        client=FakeTelegramClient("anna", 1, "hash"),
        verify_global_messaging_eligibility=AsyncMock(),
    )
    monkeypatch.setattr(run, "_pick_startup_membership_delay_seconds", lambda: 0.0)
    monkeypatch.setattr(run, "_build_group_dialog_index", AsyncMock(return_value={}))
    monkeypatch.setattr(run, "_ensure_group_membership", AsyncMock(return_value=None))
    hook = run._build_multi_group_membership_startup_hook(
        groups=[SimpleNamespace(id="missing", enabled=True, group_chat_id=-1001, group_target=None)]
    )

    with pytest.raises(run.GroupAvailabilityError, match="group_unresolved:missing"):
        await hook(SimpleNamespace(id="anna"), wrapper)


@pytest.mark.asyncio
async def test_reload_checks_new_group_for_every_active_bot_before_activation(monkeypatch):
    """Новая reload-группа активируется только после checks всех active bots."""
    import run

    clients = {
        "anna": SimpleNamespace(client=FakeTelegramClient("anna", 1, "hash")),
        "mike": SimpleNamespace(client=FakeTelegramClient("mike", 1, "hash")),
    }
    manager = SimpleNamespace(active_bot_ids=["anna", "mike"], get_client=clients.__getitem__)
    old_group = SimpleNamespace(id="old", enabled=True, group_chat_id=-1001, group_target="@old")
    new_group = SimpleNamespace(id="new", enabled=True, group_chat_id=-1002, group_target="@new")
    ensure_membership = AsyncMock(return_value=SimpleNamespace(id=1002))
    monkeypatch.setattr(run, "_build_group_dialog_index", AsyncMock(return_value={}))
    monkeypatch.setattr(run, "_ensure_group_membership", ensure_membership)
    monkeypatch.setattr(run, "_log_bot_write_permission", AsyncMock(return_value=True))

    ready = await run._filter_reload_ready_groups(manager, [old_group], [old_group, new_group])

    assert ready == [old_group, new_group]
    assert ensure_membership.await_count == 2


@pytest.mark.asyncio
async def test_reload_excludes_new_group_when_any_active_bot_cannot_write(monkeypatch):
    """Reload не включает группу при group-level отказе одного аккаунта."""
    import run

    clients = {
        "anna": SimpleNamespace(client=FakeTelegramClient("anna", 1, "hash")),
        "mike": SimpleNamespace(client=FakeTelegramClient("mike", 1, "hash")),
    }
    manager = SimpleNamespace(active_bot_ids=["anna", "mike"], get_client=clients.__getitem__)
    old_group = SimpleNamespace(id="old", enabled=True, group_chat_id=-1001, group_target="@old")
    new_group = SimpleNamespace(id="new", enabled=True, group_chat_id=-1002, group_target="@new")
    monkeypatch.setattr(run, "_build_group_dialog_index", AsyncMock(return_value={}))
    monkeypatch.setattr(run, "_ensure_group_membership", AsyncMock(return_value=SimpleNamespace(id=1002)))
    monkeypatch.setattr(run, "_log_bot_write_permission", AsyncMock(side_effect=[True, False]))

    ready = await run._filter_reload_ready_groups(manager, [old_group], [old_group, new_group])

    assert ready == [old_group]


@pytest.mark.asyncio
async def test_reload_keeps_changed_groups_pending_when_active_pool_is_empty():
    """Изменённая группа не проходит проверку vacuous truth без active bots."""
    import run

    manager = SimpleNamespace(active_bot_ids=[], get_client=Mock())
    old_group = SimpleNamespace(id="old", enabled=True, group_chat_id=-1001, group_target="@old")
    changed_group = SimpleNamespace(id="old", enabled=True, group_chat_id=-1002, group_target="@changed")

    ready = await run._filter_reload_ready_groups(manager, [old_group], [changed_group])

    assert ready == []
    manager.get_client.assert_not_called()


@pytest.mark.asyncio
async def test_dialog_index_preserves_channel_namespace_when_user_raw_id_collides():
    """Проверяет, что raw ID пользователя не вытесняет channel peer ID."""
    import run

    raw_id = 3846312748
    channel_peer_id = -1003846312748
    channel_entity = SimpleNamespace(id=raw_id, username="target_group")
    user_entity = SimpleNamespace(id=raw_id, username="unrelated_user")

    class DialogClient(FakeTelegramClient):
        async def iter_dialogs(self):
            yield SimpleNamespace(
                id=channel_peer_id,
                entity=channel_entity,
                is_group=True,
                is_channel=True,
            )
            yield SimpleNamespace(
                id=raw_id,
                entity=user_entity,
                is_group=False,
                is_channel=False,
            )

    telegram_client = DialogClient("anna", 1, "hash")
    dialog_index = await run._build_group_dialog_index(telegram_client)

    assert user_entity not in dialog_index.by_chat_id.values()

    resolved = await run._resolve_joined_group_dialog(
        telegram_client,
        raw_id,
        "@target_group",
        dialog_index=dialog_index,
    )

    assert resolved is channel_entity


@pytest.mark.asyncio
async def test_dialog_index_resolves_positive_raw_id_to_basic_group_namespace():
    """Проверяет marked `-id` для basic group при совпадении raw ID с user."""
    import run

    raw_id = 2
    basic_group_peer_id = -raw_id
    channel_peer_id = -(10**12 + raw_id)
    group_entity = SimpleNamespace(id=raw_id, title="Basic group")
    channel_entity = SimpleNamespace(id=raw_id, title="Channel")
    user_entity = SimpleNamespace(id=raw_id, username="unrelated_user")

    class DialogClient(FakeTelegramClient):
        async def iter_dialogs(self):
            yield SimpleNamespace(
                id=basic_group_peer_id,
                entity=group_entity,
                is_group=True,
                is_channel=False,
            )
            yield SimpleNamespace(
                id=channel_peer_id,
                entity=channel_entity,
                is_group=False,
                is_channel=True,
            )
            yield SimpleNamespace(
                id=raw_id,
                entity=user_entity,
                is_group=False,
                is_channel=False,
            )

    telegram_client = DialogClient("anna", 1, "hash")
    dialog_index = await run._build_group_dialog_index(telegram_client)

    resolved = await run._resolve_joined_group_dialog(
        telegram_client,
        raw_id,
        dialog_index=dialog_index,
    )

    assert resolved is group_entity


@pytest.mark.asyncio
async def test_membership_index_is_updated_after_public_join():
    """Проверяет повторное использование entity, добавленной в индекс после join."""
    import run

    joined_entity = SimpleNamespace(id=303, username="joined_group")

    class DialogClient(FakeTelegramClient):
        def __init__(self):
            super().__init__("anna", 1, "hash")
            self.iter_dialogs_calls = 0

        async def iter_dialogs(self):
            self.iter_dialogs_calls += 1
            if False:
                yield None

    telegram_client = DialogClient()
    join_group = AsyncMock(return_value=joined_entity)
    wrapper = SimpleNamespace(client=telegram_client, join_group=join_group, join_invite_link=AsyncMock())
    dialog_index = await run._build_group_dialog_index(telegram_client)

    first = await run._ensure_group_membership(
        wrapper,
        303,
        "@joined_group",
        "anna",
        dialog_index=dialog_index,
    )
    second = await run._ensure_group_membership(
        wrapper,
        303,
        "@joined_group",
        "anna",
        dialog_index=dialog_index,
    )

    assert first is joined_entity
    assert second is joined_entity
    assert telegram_client.iter_dialogs_calls == 1
    join_group.assert_awaited_once_with("@joined_group")


@pytest.mark.asyncio
async def test_membership_refreshes_dialogs_when_join_update_has_no_chat_entity():
    """Проверяет fallback dialog scan для update-контейнера без chats."""
    import run

    joined_entity = SimpleNamespace(id=404, username="joined_group")

    class UpdatesWithoutChats:
        pass

    class DialogClient(FakeTelegramClient):
        def __init__(self):
            super().__init__("anna", 1, "hash")
            self.joined = False
            self.iter_dialogs_calls = 0

        async def iter_dialogs(self):
            self.iter_dialogs_calls += 1
            if self.joined:
                yield SimpleNamespace(id=404, entity=joined_entity)

    telegram_client = DialogClient()

    async def join_public_group(_target: str):
        telegram_client.joined = True
        return UpdatesWithoutChats()

    wrapper = SimpleNamespace(
        client=telegram_client,
        join_group=AsyncMock(side_effect=join_public_group),
        join_invite_link=AsyncMock(),
    )
    dialog_index = await run._build_group_dialog_index(telegram_client)

    resolved = await run._ensure_group_membership(
        wrapper,
        404,
        "@joined_group",
        "anna",
        dialog_index=dialog_index,
    )

    assert resolved is joined_entity
    assert telegram_client.iter_dialogs_calls == 2
    assert run._find_group_in_dialog_index(dialog_index, 404, "@joined_group") is joined_entity


@pytest.mark.asyncio
async def test_resolve_group_target_caches_entities_independently_per_group():
    """Проверяет, что кэш одной группы не вытесняет entity другой группы."""
    import run

    first_entity = SimpleNamespace(id=101, username="first")
    second_entity = SimpleNamespace(id=202, username="second")

    class DialogClient(FakeTelegramClient):
        def __init__(self):
            super().__init__("anna", 1, "hash")
            self.iter_dialogs_calls = 0

        async def iter_dialogs(self):
            self.iter_dialogs_calls += 1
            yield SimpleNamespace(id=101, entity=first_entity)
            yield SimpleNamespace(id=202, entity=second_entity)

    telegram_client = DialogClient()

    assert await run._resolve_group_target(telegram_client, 101, "@first") is first_entity
    assert await run._resolve_group_target(telegram_client, 202, "@second") is second_entity
    assert await run._resolve_group_target(telegram_client, 101, "@first") is first_entity
    assert await run._resolve_group_target(telegram_client, 202, "@second") is second_entity
    assert telegram_client.iter_dialogs_calls == 2


@pytest.mark.asyncio
async def test_resolve_group_target_does_not_reuse_cache_for_changed_target():
    """Проверяет отдельный cache key после изменения target при reload."""
    import run

    first_entity = SimpleNamespace(id=101, username="first")
    second_entity = SimpleNamespace(id=202, username="second")

    class DialogClient(FakeTelegramClient):
        async def iter_dialogs(self):
            yield SimpleNamespace(id=101, entity=first_entity)
            yield SimpleNamespace(id=202, entity=second_entity)

    telegram_client = DialogClient("anna", 1, "hash")

    assert await run._resolve_group_target(telegram_client, None, "@first") is first_entity
    assert await run._resolve_group_target(telegram_client, None, "@second") is second_entity


def test_startup_membership_delay_is_selected_inside_30_to_60_seconds(monkeypatch):
    """Проверяет секундовый диапазон случайной задержки startup membership."""
    import run

    calls: list[tuple[int, int]] = []

    def fake_randint(start: int, end: int) -> int:
        calls.append((start, end))
        return 47

    monkeypatch.setattr(run, "randint", fake_randint, raising=False)

    assert run.STARTUP_MEMBERSHIP_DELAY_SECONDS == (30, 60)
    assert run._pick_startup_membership_delay_seconds() == 47.0
    assert calls == [(30, 60)]


@pytest.mark.asyncio
async def test_group_membership_startup_hook_waits_random_delay_before_join(monkeypatch):
    """Проверяет, что startup hook ждёт секундовую задержку перед membership check."""
    import run

    sleep = AsyncMock()
    ensure_membership = AsyncMock(return_value="@joined")

    monkeypatch.setattr(run.asyncio, "sleep", sleep)
    monkeypatch.setattr(run, "_ensure_group_membership", ensure_membership)
    monkeypatch.setattr(run, "_log_bot_write_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(run, "_log_bot_write_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(run, "_pick_startup_membership_delay_seconds", lambda: 45.0, raising=False)

    hook = run._build_group_membership_startup_hook(
        group_chat_id=None,
        group_target="@group",
    )

    profile = SimpleNamespace(id="anna")
    client = SimpleNamespace(client=SimpleNamespace())

    resolved = await hook(profile, client)

    assert resolved == "@joined"
    sleep.assert_awaited_once_with(45.0)
    ensure_membership.assert_awaited_once_with(client, None, "@group", "anna")


@pytest.mark.asyncio
async def test_multi_group_membership_startup_hook_waits_same_seconds_before_checks(monkeypatch):
    """Проверяет задержку startup hook перед membership всех enabled-групп."""
    import run

    sleep = AsyncMock()
    ensure_membership = AsyncMock(side_effect=["@first", "@second"])
    monkeypatch.setattr(run.asyncio, "sleep", sleep)
    monkeypatch.setattr(run, "_ensure_group_membership", ensure_membership)
    monkeypatch.setattr(run, "_log_bot_write_permission", AsyncMock(return_value=True))
    monkeypatch.setattr(run, "_pick_startup_membership_delay_seconds", lambda: 58.0, raising=False)

    hook = run._build_multi_group_membership_startup_hook(
        groups=[
            SimpleNamespace(id="first", enabled=True, group_chat_id=101, group_target="@first"),
            SimpleNamespace(id="disabled", enabled=False, group_chat_id=102, group_target="@disabled"),
            SimpleNamespace(id="second", enabled=True, group_chat_id=103, group_target="@second"),
        ],
    )

    profile = SimpleNamespace(id="anna")
    client = SimpleNamespace(client=SimpleNamespace(), verify_global_messaging_eligibility=AsyncMock())

    resolved = await hook(profile, client)

    assert resolved == {"first": "@first", "second": "@second"}
    sleep.assert_awaited_once_with(58.0)
    assert [call.args for call in ensure_membership.await_args_list] == [
        (client, 101, "@first", "anna"),
        (client, 103, "@second", "anna"),
    ]
    first_index = ensure_membership.await_args_list[0].kwargs["dialog_index"]
    assert ensure_membership.await_args_list[1].kwargs["dialog_index"] is first_index


@pytest.mark.asyncio
async def test_multi_group_startup_hook_persists_global_quarantine_for_frozen_account(monkeypatch):
    """Замороженный аккаунт передаёт manager причину quarantine до membership."""
    import run

    hook = run._build_multi_group_membership_startup_hook(
        groups=[SimpleNamespace(id="danang", enabled=True, group_chat_id=101, group_target="@group")],
    )
    root_error = RuntimeError("account frozen")
    client = SimpleNamespace(
        client=SimpleNamespace(),
        verify_global_messaging_eligibility=AsyncMock(
            side_effect=AccountMessagingUnavailableError("global messaging unavailable")
        ),
    )
    client.verify_global_messaging_eligibility.side_effect.__cause__ = root_error

    with pytest.raises(AccountMessagingUnavailableError, match="telegram_startup_global_messaging_unavailable"):
        await hook(SimpleNamespace(id="anna"), client)


class _AsyncNullContext:
    """Минимальный async context manager для тестов."""

    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False
