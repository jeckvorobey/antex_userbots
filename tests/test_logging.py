"""Тесты логирования swarm-режима."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.logging import setup_logging
from core.runtime_models import SwarmBotProfile
from userbot.orchestrator import SwarmOrchestrator
from userbot.reply_router import AddressedReplyRouter


def test_setup_logging_sets_root_level():
    """Проверяет, что настройка логирования меняет уровень root logger."""
    setup_logging("DEBUG")
    assert logging.getLogger().level == logging.DEBUG


@pytest.mark.asyncio
async def test_reply_router_logs_ignore_reason(caplog):
    """Проверяет логирование причины ignore в reply-router."""
    router = AddressedReplyRouter(
        bot_profile=SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
        history=SimpleNamespace(get_session_history=AsyncMock(), save_message=AsyncMock()),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="system")),
        ai_client=SimpleNamespace(generate_reply=AsyncMock()),
        swarm_user_ids={202, 303},
        enabled_group_chat_ids={-100555},
    )
    event = SimpleNamespace(sender_id=999, chat_id=-100555, raw_text="Привет", is_reply=False, id=77)

    with caplog.at_level(logging.DEBUG):
        handled = await router.handle_event(event)

    assert handled is False
    assert any(
        record.levelno == logging.DEBUG and "ignore non-reply" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_orchestrator_logs_skip_on_recent_human_activity(caplog):
    """Проверяет логирование skip при недавней человеческой активности."""
    orchestrator = SwarmOrchestrator(
        bot_profiles=[
            SwarmBotProfile(id="anna", session_string="anna", persona_file="anna.md", telegram_user_id=101),
            SwarmBotProfile(id="mike", session_string="mike", persona_file="mike.md", telegram_user_id=202),
        ],
        manager=SimpleNamespace(),
        topic_selector=SimpleNamespace(),
        prompt_composer=SimpleNamespace(),
        ai_client=SimpleNamespace(),
        history=SimpleNamespace(),
        exchange_store=SimpleNamespace(),
        group_target="@chat",
        skip_if_recent_human_activity=True,
        human_activity_checker=lambda: True,
    )

    with caplog.at_level(logging.INFO):
        started = await orchestrator.run_once()

    assert started is False
    assert any("recent human activity" in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_log_resolved_group_logs_configured_group_id_even_without_membership(caplog, monkeypatch):
    """Проверяет, что лог целевой группы содержит GROUP_CHAT_ID ещё до resolve membership."""
    import run

    monkeypatch.setattr(run, "_resolve_group_target", AsyncMock(return_value=None))

    with caplog.at_level(logging.INFO):
        await run._log_resolved_group(SimpleNamespace(), -1001234567890, "@chat")

    assert any(
        "Целевая группа настроена: GROUP_CHAT_ID=-1001234567890 GROUP_TARGET=@chat" in record.getMessage()
        for record in caplog.records
    )
