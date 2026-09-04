"""Регрессии выбора участников и тем между группами с общей SQLite."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ai.prompt_loader import ImportantServiceScenario
from core.runtime_models import SwarmBotProfile
from storage.sqlite_database import SQLiteDatabase
from userbot.exchange_store import ExchangeStore
from userbot.orchestrator import SwarmOrchestrator


NOW = datetime.now(UTC).replace(microsecond=0)
SCENARIOS = tuple(
    ImportantServiceScenario(key=key, question_intent=key, answer_intent="Совет")
    for key in ("exchange_rub", "booking_airbnb", "exchange_usdt", "booking_booking")
)


@pytest.fixture
async def store(monkeypatch):
    """Создаёт реальный store и фиксирует только разрешение случайных равенств."""
    monkeypatch.setattr("userbot.orchestrator.random.sample", lambda seq, n: list(seq)[:n])
    monkeypatch.setattr("userbot.orchestrator.random.choice", lambda seq: seq[0])
    database = SQLiteDatabase(":memory:")
    await database.open()
    result = ExchangeStore(database)
    await result.init_db()
    try:
        yield result
    finally:
        await database.close()


def make_orchestrator(store, group=1, bots=4, *, important=False, send=False):
    """Подменяет только Telegram, LLM и историю ответов; планирование остаётся реальным."""
    profiles = [
        SwarmBotProfile(id=f"b{i}", session_string="test", persona_file="test.md", telegram_user_id=i + 1)
        for i in range(bots)
    ]
    sent = []

    @asynccontextmanager
    async def slot(bot_id):
        if hasattr(store, "planning_lock"):
            async with asyncio.timeout(1):
                async with store.planning_lock:
                    pass
        yield send

    async def send_message(bot_id, target, text, **kwargs):
        sent.append((bot_id, target, text, kwargs))
        return SimpleNamespace(id=len(sent) + 100)

    clients = {
        p.id: SimpleNamespace(client=SimpleNamespace(
            send_message=lambda target, text, _id=p.id, **kwargs: send_message(_id, target, text, **kwargs)
        )) for p in profiles
    }
    return SwarmOrchestrator(
        bot_profiles=profiles,
        manager=SimpleNamespace(active_bot_ids=[p.id for p in profiles], scheduled_slot=slot,
                                get_client=clients.__getitem__, sent=sent),
        topic_selector=SimpleNamespace(topics=["Тема X", "Тема Y", "Тема Z"]),
        prompt_composer=SimpleNamespace(compose=AsyncMock(return_value="prompt")),
        ai_client=SimpleNamespace(start_topic=AsyncMock(return_value="Вопрос?"),
                                  generate_reply=AsyncMock(return_value="Ответ.")),
        history=SimpleNamespace(get_session_history=AsyncMock(return_value=[]), save_message=AsyncMock()),
        exchange_store=store, group_id=f"g{group}", group_chat_id=-1000 - group,
        group_target=-1000 - group, now_provider=lambda: NOW,
        important_service_scenarios=SCENARIOS if important else (),
        randint_provider=lambda low, high: low,
    )


async def records(store):
    """Возвращает сохранённые планы для проверок внешнего результата."""
    return [dict(row) for row in await store.database.fetch_all(
        "test_plans", "SELECT * FROM scheduled_exchanges ORDER BY rowid"
    )]


async def reserve(store, a, b, *, group=9, topic="Тема X", **kwargs):
    """Сохраняет предысторию обычным API."""
    return await store.create_exchange(
        initiator_bot_id=a, responder_bot_id=b, group_id=f"g{group}", group_chat_id=-1000 - group,
        topic=topic, **kwargs,
    )


@pytest.mark.parametrize("bots,groups", [(4, 2), (14, 3)])
@pytest.mark.parametrize("important", [False, True])
async def test_fresh_groups_use_distinct_participants(store, bots, groups, important):
    """Независимый random.sample повторяет первых двух ботов и нарушает эту гарантию."""
    for group in range(groups):
        await make_orchestrator(store, group, bots, important=important).run_once()
    plans = await records(store)
    assert len(plans) == groups
    assert len({p[role] for p in plans for role in ("initiator_bot_id", "responder_bot_id")}) == groups * 2


async def test_initial_scenarios_and_ordinary_topics_are_spread(store):
    """Разные новые группы не начинают все с RUB и первой обычной темы."""
    for group in range(3):
        await make_orchestrator(store, group, important=True).run_once()
    assert len({p["important_scenario"] for p in await records(store)}) == 3
    for group in range(3, 6):
        await make_orchestrator(store, group).run_once()
    assert len({p["topic_key"] for p in (await records(store))[3:]}) == 3


async def test_pair_avoidance_can_relax_local_cooldown(store):
    """Пара b0/b1 в другой группе важнее cooldown; самый недавний b3 ещё исключён."""
    await reserve(store, "b1", "b0")
    local = await reserve(store, "b2", "b3", group=1)
    await store.mark_exchange_started(local, initiator_message_id=10)
    await store.mark_exchange_completed(local, responder_message_id=11)
    orchestrator = make_orchestrator(store)
    decision = await orchestrator._build_exchange_decision()
    assert {decision.initiator.id, decision.responder.id} != {"b0", "b1"}
    assert "b3" not in {decision.initiator.id, decision.responder.id}


async def test_low_usage_and_role_rotation(store):
    """При равном cooldown выбираются менее занятые участники и роли."""
    await reserve(store, "b0", "b1", group=1)
    orchestrator = make_orchestrator(store)
    decision = await orchestrator._build_exchange_decision()
    assert {decision.initiator.id, decision.responder.id} == {"b2", "b3"}
    two = make_orchestrator(store, bots=2)
    decision = await two._build_exchange_decision()
    assert (decision.initiator.id, decision.responder.id) == ("b1", "b0")


async def test_small_roster_exhausts_pairs_before_reusing_them(store, caplog):
    """Четыре бота дают шесть разных неупорядоченных пар, затем нужен fallback."""
    caplog.set_level("INFO")
    for group in range(7):
        await make_orchestrator(store, group).run_once()
    plans = await records(store)
    assert len({frozenset((p["initiator_bot_id"], p["responder_bot_id"])) for p in plans[:6]}) == 6
    assert len(plans) == 7
    assert "pair_conflicts=1" in caplog.text


async def test_concurrent_planning_and_restart_preserve_reservations(store):
    """Общий lock защищает выбор до commit и повторное создание того же окна."""
    await asyncio.gather(*(make_orchestrator(store, g).run_once() for g in (1, 2)))
    before = await records(store)
    assert len({p[role] for p in before for role in ("initiator_bot_id", "responder_bot_id")}) == 4
    await asyncio.gather(*(make_orchestrator(store, 1).run_once() for _ in range(2)))
    assert await records(store) == before


async def test_failed_commit_leaves_no_phantom_plan(store):
    """SQLite rollback не оставляет пару занятой после ошибки сохранения."""
    await store.database.execute("test_trigger", """CREATE TRIGGER fail_plan BEFORE INSERT ON scheduled_exchanges
        BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
    with pytest.raises(Exception, match="test failure"):
        await make_orchestrator(store).run_once()
    await store.database.execute("test_drop_trigger", "DROP TRIGGER fail_plan")
    assert await records(store) == []
    await make_orchestrator(store).run_once()
    plan = (await records(store))[0]
    assert (plan["initiator_bot_id"], plan["responder_bot_id"]) == ("b0", "b1")


@pytest.mark.parametrize("status,initiator_id,responder_id,expected", [
    ("planned", None, None, ("b0", "b1")),
    ("started", 10, None, ("b0", "b1")),
    ("completed", 10, 11, ("b0", "b1")),
    ("completed", 10, None, ("b0", None)),
    ("skipped", None, None, None),
    ("skipped", 10, None, ("b0", None)),
])
async def test_summary_distinguishes_reservations_from_published_roles(
    store, status, initiator_id, responder_id, expected,
):
    """Неотправленные terminal роли не должны влиять на выбор и локальный cooldown."""
    exchange_id = await reserve(store, "b0", "b1")
    await store.database.execute("test_status", """UPDATE scheduled_exchanges
        SET status = ?, initiator_message_id = ?, responder_message_id = ? WHERE exchange_id = ?""",
        (status, initiator_id, responder_id, exchange_id))
    summary = await store.get_diversity_summary(now=NOW)
    assert [(r["initiator_bot_id"], r["responder_bot_id"]) for r in summary] == ([] if expected is None else [expected])
    assert all("question_text" not in r and "responder_text" not in r and "topic" not in r for r in summary)
    if status == "planned":
        assert await store.get_recent_bot_ids(4, group_id="g9", group_chat_id=-1009) == []


async def test_summary_expiry_identity_and_self_exclusion(store):
    """Граница 24 часов включается; анонимные и собственная запись исключаются."""
    old = await reserve(store, "b0", "b1")
    boundary = await reserve(store, "b2", "b3")
    anonymous = await store.create_exchange(initiator_bot_id="b0", responder_bot_id="b1", topic="Анонимная")
    for exchange_id, age in ((old, timedelta(days=1, seconds=1)), (boundary, timedelta(days=1))):
        await store.database.execute("test_age", "UPDATE scheduled_exchanges SET last_activity_at = ? WHERE exchange_id = ?",
                                     ((NOW - age).strftime("%Y-%m-%d %H:%M:%S"), exchange_id))
    summary = await store.get_diversity_summary(now=NOW)
    assert [r["exchange_id"] for r in summary] == [boundary]
    assert await store.get_diversity_summary(now=NOW, exclude_exchange_id=boundary) == []
    assert anonymous != boundary


async def test_same_chat_alias_does_not_create_other_group_penalty(store):
    """Другой alias той же Telegram-группы не превращает локальную пару в чужую."""
    exchange_id = await reserve(store, "b0", "b1", group=1)
    await store.database.execute("test_alias", "UPDATE scheduled_exchanges SET group_id = 'old_alias' WHERE exchange_id = ?",
                                 (exchange_id,))
    local = await reserve(store, "b2", "b3", group=1)
    await store.mark_exchange_started(local, initiator_message_id=10)
    await store.mark_exchange_completed(local, responder_message_id=11)
    decision = await make_orchestrator(store)._build_exchange_decision()
    assert {decision.initiator.id, decision.responder.id} == {"b0", "b1"}


async def test_replacement_avoids_another_group_pair_and_sends_only_responder(store):
    """Замена b1 выбирает b3, поскольку b0/b2 уже заняты другой группой."""
    await reserve(store, "b0", "b2")
    exchange_id = await reserve(store, "b0", "b1", group=1)
    await store.mark_exchange_started(exchange_id, initiator_message_id=50, question_text="Вопрос?",
                                      responder_scheduled_at=NOW)
    orchestrator = make_orchestrator(store, send=True)
    orchestrator.manager.active_bot_ids.remove("b1")
    assert await orchestrator.run_once() is True
    row = await store.get_exchange(exchange_id)
    assert row["responder_bot_id"] == "b3"
    assert row["initiator_message_id"] == 50
    assert row["status"] == "completed"
    assert [(m[0], m[3]) for m in orchestrator.manager.sent] == [("b3", {"reply_to": 50})]


async def test_initiator_replacement_keeps_responder_and_avoids_other_group_pair(store):
    """При замене инициатора направление пары сохраняет фиксированного responder."""
    await reserve(store, "b1", "b2")
    orchestrator = make_orchestrator(store, send=True)
    orchestrator.max_turns_per_exchange = 1
    orchestrator.manager.active_bot_ids.remove("b0")
    window_key, _, _ = orchestrator._build_window_key(NOW)
    exchange_id = await reserve(store, "b0", "b1", group=1, window_key=window_key)
    assert await orchestrator.run_once() is True
    row = await store.get_exchange(exchange_id)
    assert (row["initiator_bot_id"], row["responder_bot_id"]) == ("b3", "b1")
    assert row["status"] == "completed"
    assert row["responder_message_id"] is None
    assert [(m[0], m[3]) for m in orchestrator.manager.sent] == [("b3", {})]


async def test_disabled_and_unavailable_bots_never_return_for_diversity(store, caplog):
    """Fallback на повтор пары не включает аккаунты, которым запрещена работа."""
    await reserve(store, "b2", "b3")
    orchestrator = make_orchestrator(store)
    orchestrator.bot_profiles[0].enabled = False
    orchestrator.manager.active_bot_ids.remove("b1")
    caplog.set_level("INFO")
    await orchestrator.run_once()
    row = (await records(store))[-1]
    assert {row["initiator_bot_id"], row["responder_bot_id"]} == {"b2", "b3"}
    assert "pair_conflicts=1" in caplog.text
    orchestrator.disabled_bot_ids.add("b2")
    orchestrator.group_id, orchestrator.group_chat_id = "g3", -1003
    assert await orchestrator.run_once() is False
    assert len(await records(store)) == 2


async def test_topic_local_freshness_precedes_global_popularity_and_exhaustion_works(store):
    """Локальная свежесть сохраняется, а исчерпание пула не блокирует выбор."""
    local = await reserve(store, "b0", "b1", group=1, topic="Тема X")
    await store.mark_exchange_started(local, initiator_message_id=10)
    await store.mark_exchange_completed(local, responder_message_id=11)
    await reserve(store, "b2", "b3", topic="Тема Y")
    orchestrator = make_orchestrator(store)
    orchestrator.topic_selector.topics = ["Тема X", "Тема Y"]
    assert (await orchestrator._build_exchange_decision()).topic == "Тема Y"
    local_y = await reserve(store, "b0", "b1", group=1, topic="Тема Y")
    await store.mark_exchange_started(local_y, initiator_message_id=12)
    await store.mark_exchange_completed(local_y, responder_message_id=13)
    assert (await orchestrator._build_exchange_decision()).topic == "Тема X"
    orchestrator.topic_selector = SimpleNamespace(pick_random=AsyncMock(return_value="Fallback"))
    assert (await orchestrator._build_exchange_decision()).topic == "Fallback"


async def test_exhausted_initial_scenarios_and_existing_cycle(store):
    """Пятый старт допускает повтор; у действующей группы цикл и cadence сохраняются."""
    for group in range(5):
        await make_orchestrator(store, group, important=True).run_once()
    plans = await records(store)
    assert len({p["important_scenario"] for p in plans[:4]}) == 4
    assert plans[4]["important_scenario"] == "exchange_rub"
    orchestrator = make_orchestrator(store, 0, important=True)
    assert await orchestrator.run_once() is False
    assert len(await records(store)) == 5
    old_id = plans[0]["exchange_id"]
    await store.mark_exchange_started(old_id, initiator_message_id=10)
    await store.mark_exchange_completed(old_id, responder_message_id=11)
    assert await orchestrator._build_important_service_decision_if_due(NOW) is None
    old_time = (NOW - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    await store.database.execute("test_old_service", """UPDATE scheduled_exchanges
        SET completed_at = ?, last_activity_at = ? WHERE exchange_id = ?""", (old_time, old_time, old_id))
    assert (await orchestrator._build_important_service_decision_if_due(NOW)).important_scenario == "booking_airbnb"


async def test_legacy_summary_migration_and_index_are_idempotent():
    """Старая схема получает индекс и читаемую сводку, включая legacy group id."""
    database = SQLiteDatabase(":memory:")
    await database.open()
    try:
        await database.execute("test_legacy", """CREATE TABLE scheduled_exchanges (
            exchange_id TEXT PRIMARY KEY, initiator_bot_id TEXT, responder_bot_id TEXT,
            topic TEXT, status TEXT)""")
        store = ExchangeStore(database)
        await store.init_db()
        await store.init_db()
        await store.create_exchange(initiator_bot_id="b0", responder_bot_id="b1", topic="Тема", group_id="g1")
        summary = await store.get_diversity_summary(now=NOW)
        assert len(summary) == 1 and summary[0]["group_id"] == "g1"
        assert summary[0]["group_chat_id"] is None
        decision = await make_orchestrator(store)._build_exchange_decision()
        assert {decision.initiator.id, decision.responder.id} == {"b2", "b3"}
        indexes = await database.fetch_all("test_indexes", "PRAGMA index_list(scheduled_exchanges)")
        assert sum(row["name"] == "idx_scheduled_exchanges_diversity_activity" for row in indexes) == 1
    finally:
        await database.close()
