"""Central orchestrator для scheduled swarm-обменов."""

from __future__ import annotations

import logging
import random
from collections import Counter
from contextlib import nullcontext
from datetime import date
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from telethon.errors import ChannelPrivateError, ChatWriteForbiddenError, UserBannedInChannelError, UserNotParticipantError

from ai.prompt_loader import ImportantServiceScenario
from core.runtime_models import ExchangeDecision, SwarmBotProfile
from userbot.exchange_store import ExchangeStore, normalize_signature
from userbot.exchange_diversity import ExchangeDiversity
from userbot.scheduler import is_within_windows_utc, pick_random_datetime, pick_random_delay


logger = logging.getLogger(__name__)

PERMANENT_TELEGRAM_SEND_ERRORS = (
    ChannelPrivateError,
    ChatWriteForbiddenError,
    UserBannedInChannelError,
    UserNotParticipantError,
)

RECENT_BOT_COOLDOWN_LIMIT = 4
RECENT_TOPIC_LIMIT = 10
RECENT_INITIATOR_HISTORY_SCAN_LIMIT = 50
IMPORTANT_SERVICE_KIND = "important_service"
REGULAR_EXCHANGE_KIND = "regular"
IMPORTANT_SERVICE_CONTACT = "https://t.me/tt_exchenge_bot/antex"
SAFE_SCHEDULED_REPLY_FALLBACK_TEXT = "Я бы уточнил это у тех, кто сталкивался с этим совсем недавно."
SAFE_IMPORTANT_SERVICE_REPLY_FALLBACK_TEXT = (
    f"Можно обратиться сюда: {IMPORTANT_SERVICE_CONTACT} — там подскажут по обмену или оплате."
)


class SwarmOrchestrator:
    """Выбирает пары ботов и проводит A -> B exchange."""

    def __init__(
        self,
        *,
        bot_profiles: list[SwarmBotProfile],
        manager: Any,
        topic_selector: Any,
        prompt_composer: Any,
        ai_client: Any,
        history: Any,
        exchange_store: ExchangeStore | Any,
        group_id: str | None = None,
        group_city: str | None = None,
        group_target: object | None = None,
        group_chat_id: int | None = None,
        max_turns_per_exchange: int = 2,
        active_windows_utc: list[str] | None = None,
        initiator_offset_minutes: tuple[int, int] = (0, 30),
        responder_delay_minutes: tuple[int, int] = (3, 10),
        skip_if_recent_human_activity: bool = True,
        human_activity_checker: Callable[[], bool] | None = None,
        now_provider: Callable[[], Any] | None = None,
        topic_repeat_window: timedelta = timedelta(days=1),
        question_repeat_window: timedelta = timedelta(days=2),
        resolve_group_target: Callable[[object], Any] | None = None,
        randint_provider: Callable[[int, int], int] | None = None,
        allow_external_llm_for_scheduled: bool = True,
        important_service_scenarios: tuple[ImportantServiceScenario, ...] = (),
    ) -> None:
        self.bot_profiles = [profile for profile in bot_profiles if profile.enabled]
        self.disabled_bot_ids: set[str] = set()
        self.manager = manager
        self.topic_selector = topic_selector
        self.prompt_composer = prompt_composer
        self.ai_client = ai_client
        self.history = history
        self.exchange_store = exchange_store
        self.group_id = group_id
        self.group_city = group_city
        self.group_target = group_target
        self.group_chat_id = group_chat_id
        self.max_turns_per_exchange = max_turns_per_exchange
        self.active_windows_utc = active_windows_utc or []
        self.initiator_offset_minutes = initiator_offset_minutes
        self.responder_delay_minutes = responder_delay_minutes
        self.skip_if_recent_human_activity = skip_if_recent_human_activity
        self.human_activity_checker = human_activity_checker or (lambda: False)
        self.now_provider = now_provider or (lambda: datetime.now(UTC))
        self.topic_repeat_window = topic_repeat_window
        self.question_repeat_window = question_repeat_window
        self.resolve_group_target = resolve_group_target
        self.randint_provider = randint_provider or random.randint
        self.allow_external_llm_for_scheduled = allow_external_llm_for_scheduled
        self.important_service_scenarios = important_service_scenarios

    async def run_once(self) -> bool:
        """Выполняет одну due-стадию scheduled exchange."""
        now = self.now_provider()
        due_responder_getter = getattr(self.exchange_store, "get_due_started_exchange", None)
        due_responder = (
            await due_responder_getter(now=now, group_id=self.group_id, group_chat_id=self.group_chat_id)
            if callable(due_responder_getter)
            else None
        )
        if due_responder is not None:
            return await self._run_due_responder_exchange(exchange=due_responder)

        if not is_within_windows_utc(self.active_windows_utc, now):
            logger.info("orchestrator: skip exchange outside active windows now=%s", now)
            return False
        if self.skip_if_recent_human_activity and self.human_activity_checker():
            logger.info("orchestrator: skip exchange because recent human activity detected")
            return False
        if self.group_target is None:
            logger.warning("orchestrator: skip exchange because group_target is not configured")
            return False
        if self.group_id is not None and self.group_chat_id is None:
            logger.warning("orchestrator: skip exchange because resolved group_chat_id is missing group_id=%s", self.group_id)
            return False

        async with self._planning_context():
            planned_exchange = await self._get_or_plan_exchange(now)
        if planned_exchange is None:
            return False
        return await self._run_due_planned_exchange(exchange=planned_exchange, now=now)

    def _planning_context(self):
        """Возвращает общий planning lock; legacy store без координации остаётся совместимым."""
        return getattr(self.exchange_store, "planning_lock", None) or nullcontext()

    async def _get_or_plan_exchange(self, now: datetime) -> dict[str, object] | None:
        """Выбирает и сохраняет план под общим lock, не вызывая Telegram или LLM."""
        window_key, window_start, window_end = self._build_window_key(now)
        get_exchange_by_window_key = getattr(self.exchange_store, "get_exchange_by_window_key", None)
        current_window_exchange = (
            await get_exchange_by_window_key(window_key, group_id=self.group_id, group_chat_id=self.group_chat_id)
            if callable(get_exchange_by_window_key)
            else None
        )
        if current_window_exchange is not None:
            status = current_window_exchange.get("status")
            if status == "planned":
                return current_window_exchange
            logger.info(
                "orchestrator: skip new exchange because window already has status=%s window_key=%s",
                status,
                window_key,
            )
            return None

        if len(self._active_bot_profiles()) < 2:
            logger.warning("orchestrator: skip new exchange because active bot pool is smaller than two")
            return None

        decision = self._normalize_exchange_decision(await self._build_exchange_decision_for_window(now))
        logger.info(
            "orchestrator: selected pair initiator=%s responder=%s topic_key=%s kind=%s scenario=%s",
            decision.initiator.id,
            decision.responder.id,
            decision.topic_key,
            decision.exchange_kind,
            decision.important_scenario,
        )
        initiator_scheduled_at = self._pick_initiator_due_at(window_start=window_start, window_end=window_end)
        exchange_id = await self.exchange_store.create_exchange(
            group_id=self.group_id,
            group_chat_id=self.group_chat_id,
            initiator_bot_id=decision.initiator.id,
            responder_bot_id=decision.responder.id,
            topic=decision.topic,
            topic_key=decision.topic_key,
            window_key=window_key,
            initiator_scheduled_at=initiator_scheduled_at,
            exchange_kind=decision.exchange_kind,
            important_scenario=decision.important_scenario,
        )
        planned_exchange = {
            "exchange_id": exchange_id,
            "group_id": self.group_id,
            "group_chat_id": self.group_chat_id,
            "initiator_bot_id": decision.initiator.id,
            "responder_bot_id": decision.responder.id,
            "topic": decision.topic,
            "window_key": window_key,
            "initiator_scheduled_at": self._serialize_timestamp(initiator_scheduled_at),
            "exchange_kind": decision.exchange_kind,
            "important_scenario": decision.important_scenario,
        }
        return planned_exchange

    async def _build_exchange_decision_for_window(self, now: datetime) -> ExchangeDecision:
        """Выбирает important-service exchange, если он due, иначе обычный exchange."""
        important_decision = await self._build_important_service_decision_if_due(now)
        if important_decision is not None:
            return important_decision
        return await self._build_exchange_decision()

    async def _build_exchange_decision(self) -> ExchangeDecision:
        """Выбирает пару ботов и тему с persisted anti-repeat."""
        recent_bot_ids = await self.exchange_store.get_recent_bot_ids(
            RECENT_BOT_COOLDOWN_LIMIT,
            group_id=self.group_id,
            group_chat_id=self.group_chat_id,
        )
        diversity = await self._load_diversity(self.now_provider())
        chosen_initiator, chosen_responder = self._choose_participants(recent_bot_ids, diversity)

        topic = await self._choose_topic(diversity)
        recent_questions = await self.exchange_store.get_recent_questions(
            since=self.question_repeat_window,
            group_id=self.group_id,
            group_chat_id=self.group_chat_id,
        )
        return ExchangeDecision(
            initiator=chosen_initiator,
            responder=chosen_responder,
            topic=topic,
            topic_key=normalize_signature(topic),
            recent_questions=recent_questions,
        )

    async def _build_important_service_decision_if_due(self, now: datetime) -> ExchangeDecision | None:
        """Возвращает important-service decision, если группа достигла cadence."""
        if self.max_turns_per_exchange <= 1 or not self.important_service_scenarios:
            return None
        latest_getter = getattr(self.exchange_store, "get_latest_important_service_exchange", None)
        if not callable(latest_getter):
            return None

        latest_exchange = await latest_getter(group_id=self.group_id, group_chat_id=self.group_chat_id)
        if not self._important_service_is_due(latest_exchange, now):
            logger.info("orchestrator: important-service exchange is not due group_id=%s", self.group_id)
            return None

        diversity = await self._load_diversity(now)
        scenario = self._next_important_service_scenario(
            latest_exchange.get("important_scenario") if latest_exchange is not None else None,
            diversity=diversity,
        )
        recent_bot_ids = await self.exchange_store.get_recent_bot_ids(
            RECENT_BOT_COOLDOWN_LIMIT,
            group_id=self.group_id,
            group_chat_id=self.group_chat_id,
        )
        chosen_initiator, chosen_responder = self._choose_participants(recent_bot_ids, diversity)
        recent_questions = await self.exchange_store.get_recent_questions(
            since=self.question_repeat_window,
            group_id=self.group_id,
            group_chat_id=self.group_chat_id,
        )
        logger.info(
            "orchestrator: important-service selected scenario=%s group_id=%s",
            scenario.key,
            self.group_id,
        )
        return ExchangeDecision(
            initiator=chosen_initiator,
            responder=chosen_responder,
            topic=scenario.question_intent,
            topic_key=normalize_signature(f"important_service:{scenario.key}"),
            recent_questions=recent_questions,
            exchange_kind=IMPORTANT_SERVICE_KIND,
            important_scenario=scenario.key,
            important_answer_intent=scenario.answer_intent,
        )

    async def _load_diversity(self, now: datetime, *, exclude_exchange_id: str | None = None) -> ExchangeDiversity:
        """Загружает общие метаданные один раз на решение без переноса текстовой истории."""
        getter = getattr(self.exchange_store, "get_diversity_summary", None)
        if not callable(getter) or (self.group_id is None and self.group_chat_id is None):
            return ExchangeDiversity()
        rows = await getter(now=now, exclude_exchange_id=exclude_exchange_id)
        return ExchangeDiversity.from_records(rows, group_id=self.group_id, group_chat_id=self.group_chat_id)

    def _choose_participants(
        self, recent_bot_ids: list[str], diversity: ExchangeDiversity,
    ) -> tuple[SwarmBotProfile, SwarmBotProfile]:
        """Выбирает наименее повторяющуюся пару со случайным разрешением равенств."""
        candidates = (
            self._active_bot_profiles() if diversity.other_pairs else self._pick_bot_candidates(recent_bot_ids)
        )
        profiles = {profile.id: profile for profile in candidates}
        pairs = ((a, b) for a in profiles for b in profiles if a != b)
        winners, score = diversity.best_pairs(pairs, recent_bot_ids[:RECENT_BOT_COOLDOWN_LIMIT])
        if not winners:
            raise ValueError("Для scheduled exchange нужно минимум два enabled userbot")
        a, b = random.choice(winners)
        self._log_diversity_choice(a, b, score, len(winners))
        return profiles[a], profiles[b]

    def _log_diversity_choice(self, a: str, b: str, score: tuple[int, ...], candidates: int) -> None:
        """Логирует только идентификаторы и счётчики решений/ослаблений."""
        logger.info(
            "orchestrator: diversity group_id=%s initiator=%s responder=%s "
            "pair_conflicts=%s cooldown_relaxed=%s other_usage=%s total_usage=%s role_usage=%s candidates=%s",
            self.group_id, a, b, *score, candidates,
        )

    def _pick_bot_candidates(self, recent_bot_ids: list[str]) -> list[SwarmBotProfile]:
        """Возвращает кандидатов, ослабляя cooldown только если иначе пары не собрать."""
        active_profiles = self._active_bot_profiles()
        max_cooldown_size = min(RECENT_BOT_COOLDOWN_LIMIT, len(recent_bot_ids))
        profile_counts = Counter(profile.id for profile in active_profiles)
        excluded_counts = Counter(recent_bot_ids[:max_cooldown_size])
        excluded_profile_count = sum(profile_counts[bot_id] for bot_id in excluded_counts)

        for cooldown_size in range(max_cooldown_size, -1, -1):
            candidate_count = len(active_profiles) - excluded_profile_count
            if candidate_count >= 2:
                excluded_bot_ids = set(excluded_counts)
                candidates = [profile for profile in active_profiles if profile.id not in excluded_bot_ids]
                if cooldown_size < max_cooldown_size:
                    logger.info(
                        "orchestrator: relaxed recent bot cooldown cooldown_size=%s candidates=%s",
                        cooldown_size,
                        candidate_count,
                    )
                return candidates

            if cooldown_size > 0:
                restored_bot_id = recent_bot_ids[cooldown_size - 1]
                excluded_counts[restored_bot_id] -= 1
                if excluded_counts[restored_bot_id] == 0:
                    excluded_counts.pop(restored_bot_id)
                    excluded_profile_count -= profile_counts[restored_bot_id]
        raise ValueError("Для scheduled exchange нужно минимум два enabled userbot")

    async def _choose_topic(self, diversity: ExchangeDiversity | None = None) -> str:
        """Выбирает тему, избегая последних заданных тем при наличии альтернатив."""
        recent_topic_keys = await self.exchange_store.get_recent_topic_keys_by_limit(
            RECENT_TOPIC_LIMIT,
            group_id=self.group_id,
            group_chat_id=self.group_chat_id,
        )
        available_topics = list(getattr(self.topic_selector, "topics", []))
        if not available_topics:
            topic = await self.topic_selector.pick_random()
            logger.info("orchestrator: fallback topic pick via selector topic=%s", topic)
            return topic

        topic_key_getter = getattr(self.topic_selector, "topic_key", None)
        fresh_topics = [
            topic
            for topic in available_topics
            if (
                topic_key_getter(topic)
                if callable(topic_key_getter)
                else normalize_signature(topic)
            )
            not in recent_topic_keys
        ]
        diversity = diversity if diversity is not None else await self._load_diversity(self.now_provider())
        pool = fresh_topics or available_topics
        counts = [
            diversity.other_topics[topic_key_getter(topic) if callable(topic_key_getter) else normalize_signature(topic)]
            for topic in pool
        ]
        minimum = min(counts)
        topic = random.choice([topic for topic, count in zip(pool, counts) if count == minimum])
        logger.info(
            "orchestrator: topic selected topic=%s fresh_pool=%s total_pool=%s",
            topic,
            len(fresh_topics),
            len(available_topics),
        )
        return topic

    async def _run_due_planned_exchange(self, *, exchange: dict[str, object], now: datetime) -> bool:
        """Отправляет вопрос инициатора, когда пришло его окно."""
        if not self._is_due(exchange.get("initiator_scheduled_at"), now):
            logger.info(
                "orchestrator: planned exchange is waiting for initiator_due exchange_id=%s due_at=%s",
                exchange.get("exchange_id"),
                exchange.get("initiator_scheduled_at"),
            )
            return False

        initiator_id = str(exchange["initiator_bot_id"])
        responder_id = str(exchange["responder_bot_id"])
        for stage, bot_id, counterpart_bot_id in (
            ("initiator", initiator_id, responder_id),
            ("responder", responder_id, initiator_id),
        ):
            if not self._is_bot_available(bot_id):
                retry_exchange = await self._replace_unavailable_exchange_participant(
                    exchange=exchange,
                    stage=stage,
                    bot_id=bot_id,
                    counterpart_bot_id=counterpart_bot_id,
                )
                return await self._run_due_planned_exchange(exchange=retry_exchange, now=now) if retry_exchange else True
        decision = await self._build_exchange_decision_from_record(
            exchange_id=str(exchange["exchange_id"]),
            initiator_id=initiator_id,
            responder_id=responder_id,
            topic=str(exchange["topic"]),
            exchange_kind=str(exchange.get("exchange_kind") or REGULAR_EXCHANGE_KIND),
            important_scenario=(
                str(exchange["important_scenario"])
                if exchange.get("important_scenario") is not None
                else None
            ),
        )

        async with self.manager.scheduled_slot(decision.initiator.id) as initiator_acquired:
            if not initiator_acquired:
                logger.info("orchestrator: initiator busy, planned exchange will retry exchange_id=%s", exchange["exchange_id"])
                return False
            recent_questions_context = ""
            if decision.recent_questions:
                recent_questions_context = "Недавние вопросы, которые не стоит повторять:\n" + "\n".join(
                    f"- {item}" for item in decision.recent_questions[:5]
                )
            history_chat_id = self._history_chat_id(exchange)
            recent_initiator_questions = await self._get_recent_initiator_questions(
                chat_id=history_chat_id,
                bot_id=decision.initiator.id,
            )
            recent_initiator_questions_context = ""
            if recent_initiator_questions:
                recent_initiator_questions_context = "Недавние вопросы этого бота, которые не стоит повторять:\n" + "\n".join(
                    f"- {item}" for item in recent_initiator_questions
                )
            exchange_context = self._build_question_exchange_context(
                decision,
                "\n\n".join(
                    item
                    for item in (
                        recent_questions_context,
                        recent_initiator_questions_context,
                    )
                    if item
                ),
            )

            initiator_text = exchange.get("question_text")
            if not isinstance(initiator_text, str) or not initiator_text:
                initiator_prompt = await self.prompt_composer.compose(
                    "start_topic", bot_id=decision.initiator.id, persona_file=decision.initiator.persona_file,
                    exchange_context=exchange_context,
                )
                if self._allow_external_llm_for_scheduled():
                    initiator_text = await self._generate_non_repeating_question(
                        initiator_prompt=initiator_prompt, topic=decision.topic, recent_bot_questions=recent_initiator_questions,
                    )
                    if (
                        not getattr(self.ai_client, "is_output_safe", lambda _text: True)(initiator_text)
                        or (
                            decision.exchange_kind == IMPORTANT_SERVICE_KIND
                            and IMPORTANT_SERVICE_CONTACT in initiator_text
                        )
                    ):
                        initiator_text = self._build_safe_start_topic(decision.topic)
                else:
                    initiator_text = self._build_safe_start_topic(decision.topic)
                mark_generated = getattr(self.exchange_store, "mark_initiator_generated", None)
                if callable(mark_generated):
                    await mark_generated(
                        str(exchange["exchange_id"]), question_text=initiator_text, question_signature=initiator_text
                    )
            initiator_client = self.manager.get_client(decision.initiator.id)
            initiator_group_target = await self._resolve_group_target_for_client(initiator_client.client)
            try:
                initiator_message = await initiator_client.client.send_message(initiator_group_target, initiator_text)
            except PERMANENT_TELEGRAM_SEND_ERRORS as exc:
                retry_exchange = await self._handle_permanent_send_error(
                    exchange_id=str(exchange["exchange_id"]), bot_id=decision.initiator.id,
                    counterpart_bot_id=decision.responder.id, stage="initiator", exc=exc,
                )
                return await self._run_due_planned_exchange(exchange=retry_exchange, now=now) if retry_exchange else True
            responder_due_at = now + pick_random_delay(
                self.responder_delay_minutes,
                randint_provider=self.randint_provider,
            )
            await self.exchange_store.mark_exchange_started(
                str(exchange["exchange_id"]),
                initiator_message_id=getattr(initiator_message, "id", None),
                question_text=initiator_text,
                question_signature=initiator_text,
                responder_scheduled_at=responder_due_at,
            )
            history_chat_id = self._history_chat_id(exchange)
            await self.history.save_message(
                user_id=decision.initiator.telegram_user_id or 0,
                role="assistant",
                text=initiator_text,
                chat_id=history_chat_id,
                bot_id=decision.initiator.id,
                exchange_id=str(exchange["exchange_id"]),
                message_origin="scheduled_initiator",
                reply_to_message_id=None,
            )
            logger.info(
                "orchestrator: initiator sent exchange_id=%s bot_id=%s message_id=%s responder_due_at=%s",
                exchange["exchange_id"],
                decision.initiator.id,
                getattr(initiator_message, "id", None),
                responder_due_at,
            )

            if self.max_turns_per_exchange <= 1:
                await self.exchange_store.mark_exchange_completed(str(exchange["exchange_id"]))
                logger.info("orchestrator: exchange completed without responder exchange_id=%s", exchange["exchange_id"])
        return True

    async def _get_recent_initiator_questions(self, *, chat_id: int | None, bot_id: str) -> list[str]:
        """Возвращает последние scheduled вопросы конкретного initiator-бота в группе."""
        getter = getattr(self.history, "get_session_history", None)
        if not callable(getter):
            return []
        history_rows = await getter(
            chat_id=chat_id,
            bot_id=bot_id,
            limit=RECENT_INITIATOR_HISTORY_SCAN_LIMIT,
        )
        questions = [
            str(item["text"])
            for item in history_rows
            if item.get("message_origin") == "scheduled_initiator" and isinstance(item.get("text"), str)
        ]
        questions = questions[-5:]
        logger.info(
            "orchestrator: loaded recent initiator questions chat_id=%s bot_id=%s count=%s",
            chat_id,
            bot_id,
            len(questions),
        )
        return questions

    async def _run_due_responder_exchange(self, *, exchange: dict[str, object]) -> bool:
        """Отправляет отложенный ответ второго бота."""
        if self.max_turns_per_exchange <= 1:
            await self.exchange_store.mark_exchange_completed(str(exchange["exchange_id"]))
            logger.info("orchestrator: completed stale started exchange without responder exchange_id=%s", exchange["exchange_id"])
            return True

        responder_id = str(exchange["responder_bot_id"])
        initiator_id = str(exchange["initiator_bot_id"])
        if not self._is_bot_available(responder_id):
            retry_exchange = await self._replace_unavailable_exchange_participant(
                exchange=exchange,
                stage="responder",
                bot_id=responder_id,
                counterpart_bot_id=initiator_id,
            )
            return await self._run_due_responder_exchange(exchange=retry_exchange) if retry_exchange else True
        async with self.manager.scheduled_slot(responder_id) as responder_acquired:
            if not responder_acquired:
                logger.info("orchestrator: responder busy, due reply will retry exchange_id=%s", exchange["exchange_id"])
                return False

            responder = self._get_bot_profile(responder_id)
            responder_text = exchange.get("responder_text")
            history_chat_id = self._history_chat_id(exchange)
            if not isinstance(responder_text, str) or not responder_text:
                responder_prompt = await self.prompt_composer.compose(
                    "reply", bot_id=responder.id, persona_file=responder.persona_file,
                    exchange_context=self._build_responder_exchange_context(exchange),
                )
                responder_history = await self.history.get_session_history(chat_id=history_chat_id, bot_id=responder.id)
                if self._allow_external_llm_for_scheduled():
                    responder_text = await self.ai_client.generate_reply(
                        system_prompt=responder_prompt, history=responder_history, user_message=str(exchange["question_text"]),
                    )
                    if (
                        not getattr(self.ai_client, "is_output_safe", lambda _text: True)(responder_text)
                        or (
                            exchange.get("exchange_kind") == IMPORTANT_SERVICE_KIND
                            and IMPORTANT_SERVICE_CONTACT not in responder_text
                        )
                    ):
                        responder_text = self._responder_fallback_text(exchange)
                else:
                    responder_text = self._responder_fallback_text(exchange)
                mark_generated = getattr(self.exchange_store, "mark_responder_generated", None)
                if callable(mark_generated):
                    await mark_generated(str(exchange["exchange_id"]), responder_text)
            responder_client = self.manager.get_client(responder.id)
            reply_to_message_id = exchange.get("initiator_message_id")
            responder_group_target = await self._resolve_group_target_for_client(responder_client.client)
            try:
                responder_message = await responder_client.client.send_message(
                    responder_group_target,
                    responder_text,
                    reply_to=reply_to_message_id,
                )
            except PERMANENT_TELEGRAM_SEND_ERRORS as exc:
                retry_exchange = await self._handle_permanent_send_error(
                    exchange_id=str(exchange["exchange_id"]), bot_id=responder.id,
                    counterpart_bot_id=initiator_id, stage="responder", exc=exc,
                )
                return await self._run_due_responder_exchange(exchange=retry_exchange) if retry_exchange else True
            await self.history.save_message(
                user_id=responder.telegram_user_id or 0,
                role="assistant",
                text=responder_text,
                chat_id=history_chat_id,
                bot_id=responder.id,
                exchange_id=str(exchange["exchange_id"]),
                message_origin="scheduled_responder",
                reply_to_message_id=reply_to_message_id,
            )
            logger.info(
                "orchestrator: responder sent exchange_id=%s bot_id=%s reply_to=%s initiator=%s",
                exchange["exchange_id"],
                responder.id,
                reply_to_message_id,
                initiator_id,
            )

        responder_message_id = getattr(responder_message, "id", None)
        if isinstance(responder_message_id, int):
            await self.exchange_store.mark_exchange_completed(
                str(exchange["exchange_id"]),
                responder_message_id=responder_message_id,
            )
        else:
            await self.exchange_store.mark_exchange_completed(str(exchange["exchange_id"]))
        logger.info("orchestrator: exchange completed exchange_id=%s", exchange["exchange_id"])
        return True

    @staticmethod
    def _responder_fallback_text(exchange: dict[str, object]) -> str:
        """Выбирает безопасный fallback с учётом типа scheduled exchange."""
        if exchange.get("exchange_kind") == IMPORTANT_SERVICE_KIND:
            return SAFE_IMPORTANT_SERVICE_REPLY_FALLBACK_TEXT
        return SAFE_SCHEDULED_REPLY_FALLBACK_TEXT

    async def _handle_permanent_send_error(
        self, *, exchange_id: str, bot_id: str, counterpart_bot_id: str, stage: str, exc: Exception
    ) -> dict[str, object] | None:
        """Отключает заблокированный аккаунт и переносит turn на доступную персону."""
        reason = f"telegram_{stage}_send_forbidden:{type(exc).__name__}"
        logger.warning(
            "orchestrator: permanent Telegram send error exchange_id=%s bot_id=%s group_id=%s stage=%s action=quarantine",
            exchange_id, bot_id, self.group_id, stage,
        )
        self.disabled_bot_ids.add(bot_id)
        quarantine_error: Exception | None = None
        quarantine_bot = getattr(self.exchange_store, "quarantine_bot", None)
        if callable(quarantine_bot):
            group_key = str(self.group_chat_id if self.group_chat_id is not None else self.group_target)
            try:
                await quarantine_bot(group_key=group_key, bot_id=bot_id, reason=reason)
            except Exception as persist_exc:
                quarantine_error = persist_exc
                logger.error(
                    "orchestrator: quarantine persistence failed bot_id=%s group_id=%s "
                    "action=disable_before_propagate",
                    bot_id,
                    self.group_id,
                )
        manager_disable = getattr(self.manager, "disable_bot", None)
        if callable(manager_disable):
            await manager_disable(bot_id, reason=reason)
        if quarantine_error is not None:
            raise quarantine_error
        return await self._reassign_participant(
            exchange_id=exchange_id, bot_id=bot_id, counterpart_bot_id=counterpart_bot_id,
            stage=stage, reason=reason,
        )

    async def _replace_unavailable_exchange_participant(
        self,
        *,
        exchange: dict[str, object],
        stage: str,
        bot_id: str,
        counterpart_bot_id: str,
    ) -> dict[str, object] | None:
        """Заменяет устаревшего участника exchange без вызова LLM и падения scheduler."""
        exchange_id = str(exchange["exchange_id"])
        reason = f"scheduled_{stage}_bot_unavailable"
        logger.warning(
            "orchestrator: unavailable persisted participant exchange_id=%s bot_id=%s group_id=%s stage=%s action=reassign",
            exchange_id,
            bot_id,
            self.group_id,
            stage,
        )
        return await self._reassign_participant(
            exchange_id=exchange_id, bot_id=bot_id, counterpart_bot_id=counterpart_bot_id,
            stage=stage, reason=reason,
        )

    async def _reassign_participant(
        self, *, exchange_id: str, bot_id: str, counterpart_bot_id: str, stage: str, reason: str,
    ) -> dict[str, object] | None:
        """Согласует выбор замены и сохранение нового резерва между группами."""
        async with self._planning_context():
            replacement = await self._pick_replacement_bot(
                failed_bot_id=bot_id, counterpart_bot_id=counterpart_bot_id,
                stage=stage, exchange_id=exchange_id,
            )
            reassign = getattr(self.exchange_store, "reassign_after_permanent_send_error", None)
            get_exchange = getattr(self.exchange_store, "get_exchange", None)
            if replacement is not None and callable(reassign) and callable(get_exchange):
                await reassign(
                    exchange_id, stage=stage, replacement_bot_id=replacement.id,
                    counterpart_bot_id=counterpart_bot_id,
                )
                return await get_exchange(exchange_id)
            await self.exchange_store.mark_exchange_skipped(exchange_id, reason)
            logger.warning(
                "orchestrator: skipped exchange without replacement exchange_id=%s bot_id=%s stage=%s",
                exchange_id, bot_id, stage,
            )
            return None

    def _active_bot_profiles(self) -> list[SwarmBotProfile]:
        """Возвращает доступные для scheduled exchange аккаунты."""
        active_ids = getattr(self.manager, "active_bot_ids", None)
        return [
            profile for profile in self.bot_profiles
            if profile.enabled and profile.id not in self.disabled_bot_ids and (active_ids is None or profile.id in active_ids)
        ]

    def _is_bot_available(self, bot_id: str) -> bool:
        """Проверяет, можно ли использовать persisted bot_id в scheduled exchange."""
        try:
            profile = self._get_bot_profile(bot_id)
        except KeyError:
            return False
        if not profile.enabled or bot_id in self.disabled_bot_ids:
            return False
        is_active = getattr(self.manager, "is_active", None)
        if callable(is_active):
            return bool(is_active(bot_id))
        active_ids = getattr(self.manager, "active_bot_ids", None)
        return active_ids is None or bot_id in active_ids

    async def _pick_replacement_bot(
        self, *, failed_bot_id: str, counterpart_bot_id: str, stage: str, exchange_id: str,
    ) -> SwarmBotProfile | None:
        """Выбирает замену с фиксированным counterpart, исключая собственный резерв."""
        profiles = {
            profile.id: profile for profile in self._active_bot_profiles()
            if profile.id not in {failed_bot_id, counterpart_bot_id}
        }
        if not profiles:
            return None
        diversity = await self._load_diversity(self.now_provider(), exclude_exchange_id=exchange_id)
        recent_getter = getattr(self.exchange_store, "get_recent_bot_ids", None)
        recent_ids = (
            await recent_getter(RECENT_BOT_COOLDOWN_LIMIT, group_id=self.group_id, group_chat_id=self.group_chat_id)
            if callable(recent_getter) else []
        )
        pairs = (
            (bot_id, counterpart_bot_id) if stage == "initiator" else (counterpart_bot_id, bot_id)
            for bot_id in profiles
        )
        winners, score = diversity.best_pairs(pairs, recent_ids[:RECENT_BOT_COOLDOWN_LIMIT])
        a, b = random.choice(winners)
        self._log_diversity_choice(a, b, score, len(winners))
        return profiles[a if stage == "initiator" else b]

    async def _resolve_group_target_for_client(self, telegram_client: object) -> object:
        """Резолвит entity группы отдельно для каждого Telethon-клиента."""
        if self.resolve_group_target is None:
            return self.group_target

        resolved_target = await self.resolve_group_target(telegram_client)
        if resolved_target is None:
            logger.warning("orchestrator: fallback to shared group_target because per-client resolve returned None")
            return self.group_target
        return resolved_target

    async def _generate_non_repeating_question(
        self,
        *,
        initiator_prompt: str,
        topic: str,
        recent_bot_questions: list[str] | None = None,
    ) -> str:
        """Генерирует вопрос и старается избежать повтора по recent signature."""
        recent_signatures = await self.exchange_store.get_recent_question_signatures(
            since=self.question_repeat_window,
            group_id=self.group_id,
            group_chat_id=self.group_chat_id,
        )
        recent_signatures.update(normalize_signature(item) for item in recent_bot_questions or [])

        prompt = initiator_prompt
        current_topic = topic
        available_topics = list(getattr(self.topic_selector, "topics", []))
        tried_topics = {topic}

        for attempt in range(1, 4):
            question_text = await self.ai_client.start_topic(system_prompt=prompt, topic=current_topic)
            signature = normalize_signature(question_text)
            if signature not in recent_signatures:
                return question_text
            logger.info("orchestrator: repeated question signature detected attempt=%s topic=%s", attempt, current_topic)
            alternative_topics = [candidate for candidate in available_topics if candidate not in tried_topics]
            if alternative_topics:
                current_topic = random.choice(alternative_topics)
                tried_topics.add(current_topic)
                prompt = initiator_prompt
                logger.info(
                    "orchestrator: retrying scheduled question with alternative topic topic=%s remaining=%s",
                    current_topic,
                    len(alternative_topics) - 1,
                )
                continue
            prompt = f"{initiator_prompt}\n\nНе повторяй недавние формулировки. Скажи по-другому и естественнее."
        return question_text

    async def _build_exchange_decision_from_record(
        self,
        *,
            exchange_id: str,
            initiator_id: str,
            responder_id: str,
            topic: str,
            exchange_kind: str = REGULAR_EXCHANGE_KIND,
            important_scenario: str | None = None,
    ) -> ExchangeDecision:
        """Восстанавливает ExchangeDecision из persisted exchange."""
        recent_questions = await self.exchange_store.get_recent_questions(
            since=self.question_repeat_window,
            group_id=self.group_id,
            group_chat_id=self.group_chat_id,
        )
        logger.info(
            "orchestrator: restoring persisted exchange exchange_id=%s initiator=%s responder=%s",
            exchange_id,
            initiator_id,
            responder_id,
        )
        return ExchangeDecision(
            initiator=self._get_bot_profile(initiator_id),
            responder=self._get_bot_profile(responder_id),
            topic=topic,
            topic_key=normalize_signature(topic),
            recent_questions=recent_questions,
            exchange_kind=exchange_kind,
            important_scenario=important_scenario,
            important_answer_intent=self._important_service_answer_intent(important_scenario),
        )

    @staticmethod
    def _normalize_exchange_decision(decision: object) -> ExchangeDecision:
        """Добавляет defaults для старых test doubles ExchangeDecision."""
        if isinstance(decision, ExchangeDecision):
            return decision
        return ExchangeDecision(
            initiator=getattr(decision, "initiator"),
            responder=getattr(decision, "responder"),
            topic=getattr(decision, "topic"),
            topic_key=getattr(decision, "topic_key"),
            recent_questions=list(getattr(decision, "recent_questions", [])),
            exchange_kind=getattr(decision, "exchange_kind", REGULAR_EXCHANGE_KIND),
            important_scenario=getattr(decision, "important_scenario", None),
            important_answer_intent=getattr(decision, "important_answer_intent", None),
        )

    def _build_question_exchange_context(self, decision: ExchangeDecision, recent_questions_context: str) -> str:
        """Строит prompt-context для вопроса initiator-а."""
        if decision.exchange_kind != IMPORTANT_SERVICE_KIND:
            return self._build_exchange_context(recent_questions_context)

        body = "\n".join(
            item
            for item in (
                "important_service_question",
                f"important_scenario: {decision.important_scenario}",
                f"question_intent: {decision.topic}",
                recent_questions_context,
            )
            if item
        )
        return self._build_exchange_context(body)

    def _build_responder_exchange_context(self, exchange: dict[str, object]) -> str:
        """Строит prompt-context для ответа responder-а."""
        base = f"Тема обмена: {exchange['topic']}\nСообщение инициатора: {exchange['question_text']}"
        if exchange.get("exchange_kind") != IMPORTANT_SERVICE_KIND:
            return self._build_exchange_context(base)

        scenario_key = str(exchange.get("important_scenario") or "")
        answer_intent = self._important_service_answer_intent(scenario_key)
        body = "\n".join(
            item
            for item in (
                "important_service_answer",
                f"important_scenario: {scenario_key}",
                f"answer_intent: {answer_intent}",
                base,
            )
            if item
        )
        return self._build_exchange_context(body)

    def _next_important_service_scenario(
        self, latest_scenario: object | None, *, diversity: ExchangeDiversity | None = None,
    ) -> ImportantServiceScenario:
        """Разносит стартовые позиции групп, затем продолжает persisted цикл."""
        scenario_keys = [scenario.key for scenario in self.important_service_scenarios]
        if not isinstance(latest_scenario, str) or latest_scenario not in scenario_keys:
            counts = (diversity or ExchangeDiversity()).other_scenarios
            minimum = min(counts[key] for key in scenario_keys)
            return random.choice([scenario for scenario in self.important_service_scenarios if counts[scenario.key] == minimum])
        next_index = (scenario_keys.index(latest_scenario) + 1) % len(self.important_service_scenarios)
        return self.important_service_scenarios[next_index]

    def _important_service_answer_intent(self, scenario_key: str | None) -> str | None:
        """Возвращает answer intent по ключу important-service сценария."""
        for scenario in self.important_service_scenarios:
            if scenario.key == scenario_key:
                return scenario.answer_intent
        return None

    def _important_service_is_due(self, latest_exchange: dict[str, object] | None, now: datetime) -> bool:
        """Проверяет per-group cadence: N, N+1, N+2 закрыты; N+3 доступен."""
        if latest_exchange is None:
            return True
        latest_date = self._important_exchange_date(latest_exchange)
        if latest_date is None:
            return True
        return (now.astimezone(UTC).date() - latest_date).days >= 3

    @classmethod
    def _important_exchange_date(cls, exchange: dict[str, object]) -> date | None:
        """Достаёт UTC date из persisted lifecycle timestamps."""
        for key in ("completed_at", "started_at", "created_at"):
            raw_timestamp = exchange.get(key)
            if raw_timestamp is None:
                continue
            return cls._parse_sqlite_timestamp(raw_timestamp).astimezone(UTC).date()
        return None

    def _get_bot_profile(self, bot_id: str) -> SwarmBotProfile:
        """Возвращает профиль активного бота по id."""
        for profile in self.bot_profiles:
            if profile.id == bot_id:
                return profile
        raise KeyError(bot_id)

    def _pick_initiator_due_at(self, *, window_start: datetime, window_end: datetime) -> datetime:
        """Выбирает момент первого сообщения внутри активного окна."""
        if not self.active_windows_utc:
            return self.now_provider()
        return pick_random_datetime(
            window_start,
            window_end,
            now=self.now_provider(),
            randint_provider=self.randint_provider,
        )

    def _build_exchange_context(self, body: str | None = None) -> str:
        """Добавляет к prompt-контексту сведения о группе."""
        parts: list[str] = []
        if self.group_city or self.group_id:
            parts.append(
                "Контекст группы: "
                + ", ".join(
                    item
                    for item in (
                        f"город: {self.group_city}" if self.group_city else None,
                        f"group_id: {self.group_id}" if self.group_id else None,
                    )
                    if item
                )
            )
        if body and body.strip():
            parts.append(body.strip())
        return "\n".join(parts)

    def _allow_external_llm_for_scheduled(self) -> bool:
        """Проверяет, разрешён ли внешний LLM для scheduled exchange."""
        return bool(getattr(self, "allow_external_llm_for_scheduled", True))

    @staticmethod
    def _build_safe_start_topic(topic: str) -> str:
        """Строит безопасный локальный fallback для инициатора."""
        normalized = topic.strip().rstrip(".!?")
        if not normalized:
            return "Кто может подсказать по этой теме?"
        if topic.strip().endswith("?"):
            return topic.strip()
        return f"Кто может подсказать: {normalized.lower()}?"

    def _history_chat_id(self, exchange: dict[str, object]) -> int | None:
        """Возвращает реальный chat_id группы для истории."""
        raw_chat_id = exchange.get("group_chat_id", self.group_chat_id)
        return raw_chat_id if isinstance(raw_chat_id, int) else self.group_chat_id

    def _build_window_key(self, now: datetime) -> tuple[str, datetime, datetime]:
        """Строит persisted ключ текущего активного окна."""
        if not self.active_windows_utc:
            start = now.replace(minute=0, second=0, microsecond=0)
            return f"{start.strftime('%Y-%m-%dT%H')}:always-open", start, now

        for window in self.active_windows_utc:
            start_hour, end_hour = (int(part) for part in window.split("-", maxsplit=1))
            if self._hour_is_within_window(now.hour, start_hour, end_hour):
                start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
                if start_hour > end_hour and now.hour < end_hour:
                    start -= timedelta(days=1)
                duration_hours = (end_hour - start_hour) % 24
                end = start + timedelta(hours=duration_hours)
                return f"{start.strftime('%Y-%m-%dT%H')}:{window}", start, end
        start = now.replace(minute=0, second=0, microsecond=0)
        return f"{start.strftime('%Y-%m-%dT%H')}:fallback", start, now

    @staticmethod
    def _hour_is_within_window(current_hour: int, start_hour: int, end_hour: int) -> bool:
        """Проверяет попадание часа в UTC-окно."""
        if start_hour == end_hour:
            return True
        if start_hour < end_hour:
            return start_hour <= current_hour < end_hour
        return current_hour >= start_hour or current_hour < end_hour

    @staticmethod
    def _is_due(raw_timestamp: object, now: datetime) -> bool:
        """Проверяет, наступил ли due timestamp из SQLite."""
        if raw_timestamp is None:
            return True
        due_at = SwarmOrchestrator._parse_sqlite_timestamp(raw_timestamp)
        return due_at <= now.astimezone(UTC)

    @staticmethod
    def _parse_sqlite_timestamp(raw_timestamp: object) -> datetime:
        """Парсит SQLite timestamp как UTC-aware datetime."""
        if isinstance(raw_timestamp, datetime):
            value = raw_timestamp
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return datetime.strptime(str(raw_timestamp), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)

    @staticmethod
    def _serialize_timestamp(value: datetime | None) -> str | None:
        """Преобразует datetime в строку SQLite-формата."""
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
