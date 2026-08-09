"""Тесты менеджера swarm-клиентов."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.runtime_models import SwarmBotProfile
from userbot.client import AccountMessagingUnavailableError
from userbot.swarm_manager import SwarmManager


@pytest.mark.asyncio
async def test_swarm_manager_starts_enabled_bots_and_collects_user_ids():
    """Проверяет запуск enabled-ботов и сбор их Telegram user_id."""
    anna_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )
    john_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=202)),
        run_until_disconnected=AsyncMock(),
    )

    manager = SwarmManager(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", enabled=True),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", enabled=False),
            SwarmBotProfile(id="john", session_string="john", persona_file="john.md", enabled=True),
        ],
        client_factory=lambda profile: anna_client if profile.id == "anna" else john_client,
    )

    await manager.start()

    anna_client.start.assert_awaited_once()
    john_client.start.assert_awaited_once()
    assert manager.swarm_user_ids == {101, 202}
    assert sorted(manager.active_bot_ids) == ["anna", "john"]


@pytest.mark.asyncio
async def test_swarm_manager_disables_bot_after_permanent_send_error():
    """Отключённый runtime-бот больше не считается активным и его клиент останавливается."""
    fake_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )
    manager = SwarmManager(
        bot_profiles=[SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md")],
        client_factory=lambda _profile: fake_client,
    )
    await manager.start()

    await manager.disable_bot("anna", reason="telegram_responder_send_forbidden:UserBannedInChannelError")

    assert manager.is_active("anna") is False
    assert manager.runtime_states["anna"].status == "disabled"
    assert manager.swarm_user_ids == {101}
    fake_client.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_swarm_manager_disables_frozen_bot_when_global_messaging_check_fails():
    """Глобально недоступный аккаунт останавливается и требует ручной проверки."""
    fake_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )

    async def startup_hook(_profile, _client):
        raise AccountMessagingUnavailableError("telegram_startup_global_messaging_unavailable:UserDeactivatedBanError")

    quarantine_bot = AsyncMock()
    manager = SwarmManager(
        bot_profiles=[SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md")],
        client_factory=lambda _profile: fake_client,
        startup_hook=startup_hook,
        startup_quarantine_bot=quarantine_bot,
    )

    await manager.start()

    assert manager.active_bot_ids == []
    assert manager.runtime_states["anna"].status == "disabled"
    assert manager.runtime_states["anna"].last_error_text == "telegram_startup_global_messaging_unavailable:UserDeactivatedBanError"
    fake_client.stop.assert_awaited_once()
    quarantine_bot.assert_awaited_once_with(
        "anna", "telegram_startup_global_messaging_unavailable:UserDeactivatedBanError"
    )


@pytest.mark.asyncio
async def test_swarm_manager_stops_startup_when_global_quarantine_cannot_be_persisted():
    """Подтверждённо frozen-аккаунт не допускает запуск без durable quarantine."""
    anna_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )
    john_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=202)),
        run_until_disconnected=AsyncMock(),
    )

    async def startup_hook(profile, _client):
        if profile.id == "anna":
            raise AccountMessagingUnavailableError("global messaging unavailable")

    quarantine_bot = AsyncMock(side_effect=RuntimeError("sqlite unavailable"))
    manager = SwarmManager(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md"),
            SwarmBotProfile(id="john", session_string="john", persona_file="john.md"),
        ],
        client_factory=lambda profile: anna_client if profile.id == "anna" else john_client,
        startup_hook=startup_hook,
        startup_quarantine_bot=quarantine_bot,
    )

    with pytest.raises(RuntimeError, match="sqlite unavailable"):
        await manager.start()

    assert manager.active_bot_ids == ["john"]
    assert manager.runtime_states["anna"].status == "disabled"
    anna_client.stop.assert_awaited_once()
    john_client.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_swarm_manager_quarantines_frozen_bot_during_reconnect():
    """Health-check после reconnect сохраняет quarantine и исключает аккаунт из пула."""
    fake_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )
    startup_hook = AsyncMock(
        side_effect=[None, AccountMessagingUnavailableError("global messaging unavailable")]
    )
    quarantine_bot = AsyncMock()
    profile = SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md")
    manager = SwarmManager(
        bot_profiles=[profile],
        client_factory=lambda _profile: fake_client,
        startup_hook=startup_hook,
        startup_quarantine_bot=quarantine_bot,
        reconnect_backoff_seconds=(0.0,),
    )
    await manager.start()

    await manager._reconnect_bot(profile, manager.runtime_states["anna"], RuntimeError("disconnect"))

    assert manager.is_active("anna") is False
    assert manager.runtime_states["anna"].status == "disabled"
    quarantine_bot.assert_awaited_once_with("anna", "global messaging unavailable")


@pytest.mark.asyncio
async def test_swarm_manager_rejects_scheduled_slot_for_unavailable_bot():
    """Недоступный bot_id не должен приводить к KeyError при попытке взять scheduled slot."""
    manager = SwarmManager(bot_profiles=[], client_factory=lambda _profile: None)

    async with manager.scheduled_slot("missing") as acquired:
        assert acquired is False


@pytest.mark.asyncio
async def test_swarm_manager_prioritizes_human_slot_over_scheduled():
    """Проверяет, что scheduled задача уступает human reply."""
    fake_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )
    manager = SwarmManager(
        bot_profiles=[SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md")],
        client_factory=lambda _profile: fake_client,
    )
    await manager.start()

    human_entered = asyncio.Event()
    scheduled_result: list[bool] = []

    async def human_task():
        async with manager.human_slot("anna"):
            human_entered.set()
            await asyncio.sleep(0)

    async def scheduled_task():
        await human_entered.wait()
        async with manager.scheduled_slot("anna") as acquired:
            scheduled_result.append(acquired)

    await asyncio.gather(human_task(), scheduled_task())

    assert scheduled_result == [False]


@pytest.mark.asyncio
async def test_swarm_manager_reconnects_after_client_error():
    """Проверяет reconnect loop после ошибки клиента."""
    stop_signal = asyncio.Event()

    async def failing_run():
        if not stop_signal.is_set():
            stop_signal.set()
            raise RuntimeError("boom")
        return None

    fake_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(side_effect=failing_run),
    )
    profile = SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md")
    manager = SwarmManager(
        bot_profiles=[profile],
        client_factory=lambda _profile: fake_client,
        reconnect_backoff_seconds=(0.0,),
    )
    await manager.start()

    supervise_task = asyncio.create_task(manager.supervise_bot("anna"))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await manager.stop()
    supervise_task.cancel()
    await asyncio.gather(supervise_task, return_exceptions=True)

    assert fake_client.start.await_count >= 2
    assert manager.runtime_states["anna"].reconnect_attempts >= 1


@pytest.mark.asyncio
async def test_swarm_manager_excludes_bot_from_active_pool_during_reconnect_startup_hook():
    """Новый reconnect-клиент не доступен scheduler до health-check и membership."""
    fake_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )
    hook_active_states: list[bool] = []
    profile = SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md")

    async def startup_hook(started_profile, _client):
        hook_active_states.append(started_profile.id in manager.active_bot_ids)

    manager = SwarmManager(
        bot_profiles=[profile],
        client_factory=lambda _profile: fake_client,
        startup_hook=startup_hook,
        reconnect_backoff_seconds=(0.0,),
    )
    await manager.start()

    await manager._reconnect_bot(profile, manager.runtime_states["anna"], RuntimeError("disconnect"))

    assert hook_active_states == [False, False]
    assert manager.active_bot_ids == ["anna"]


@pytest.mark.asyncio
async def test_swarm_manager_skips_bot_when_startup_fails():
    """Проверяет, что бот с ошибкой startup не попадает в активный пул."""
    anna_client = SimpleNamespace(
        start=AsyncMock(side_effect=RuntimeError("join failed")),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=101)),
        run_until_disconnected=AsyncMock(),
    )
    john_client = SimpleNamespace(
        start=AsyncMock(),
        stop=AsyncMock(),
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=202)),
        run_until_disconnected=AsyncMock(),
    )

    manager = SwarmManager(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", enabled=True),
            SwarmBotProfile(id="john", session_string="john", persona_file="john.md", enabled=True),
        ],
        client_factory=lambda profile: anna_client if profile.id == "anna" else john_client,
    )

    await manager.start()

    assert manager.active_bot_ids == ["john"]
    assert set(manager.clients) == {"john"}
    assert manager.swarm_user_ids == {202}
    assert manager.runtime_states["anna"].status == "error"
