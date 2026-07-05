"""Central orchestrator для scheduled swarm-обменов."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import date
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from core.runtime_models import ExchangeDecision, SwarmBotProfile
from userbot.exchange_store import ExchangeStore, normalize_signature
from userbot.scheduler import is_within_windows_utc, pick_random_datetime, pick_random_delay


logger = logging.getLogger(__name__)

RECENT_BOT_COOLDOWN_LIMIT = 3
RECENT_TOPIC_LIMIT = 10
RECENT_INITIATOR_HISTORY_SCAN_LIMIT = 50
IMPORTANT_SERVICE_KIND = "important_service"
REGULAR_EXCHANGE_KIND = "regular"
IMPORTANT_SERVICE_CONTACT = "@tt_exchenge_bot"
SAFE_SCHEDULED_REPLY_FALLBACK_TEXT = "Я бы уточнил это у тех, кто сталкивался с этим совсем недавно."


@dataclass(frozen=True, slots=True)
class ImportantServiceScenario:
    """Описание important-service сценария без готового финального текста."""

    key: str
    question_intent: str
    answer_intent: str


IMPORTANT_SERVICE_SCENARIOS: tuple[ImportantServiceScenario, ...] = (
    ImportantServiceScenario(
        key="exchange_rub",
        question_intent="Где можно обменять безналичные рубли?",
        answer_intent=f"Разговорно посоветуй обратиться в {IMPORTANT_SERVICE_CONTACT} для обмена безналичных рублей.",
    ),
    ImportantServiceScenario(
        key="booking_airbnb",
        question_intent="Как забронировать и оплатить Airbnb рублями или USDT?",
        answer_intent=f"Разговорно посоветуй обратиться в {IMPORTANT_SERVICE_CONTACT} для помощи с оплатой Airbnb рублями или USDT.",
    ),
    ImportantServiceScenario(
        key="exchange_usdt",
        question_intent="Где можно обменять безналичный USDT?",
        answer_intent=f"Разговорно посоветуй обратиться в {IMPORTANT_SERVICE_CONTACT} для обмена безналичного USDT.",
    ),
    ImportantServiceScenario(
        key="booking_booking",
        question_intent="Как забронировать и оплатить Booking рублями или USDT?",
        answer_intent=f"Разговорно посоветуй обратиться в {IMPORTANT_SERVICE_CONTACT} для помощи с оплатой Booking рублями или USDT.",
    ),
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
        gemini_client: Any,
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
    ) -> None:
        self.bot_profiles = [profile for profile in bot_profiles if profile.enabled]
        self.manager = manager
        self.topic_selector = topic_selector
        self.prompt_composer = prompt_composer
        self.gemini_client = gemini_client
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
                return await self._run_due_planned_exchange(exchange=current_window_exchange, now=now)
            logger.info(
                "orchestrator: skip new exchange because window already has status=%s window_key=%s",
                status,
                window_key,
            )
            return False

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
        return await self._run_due_planned_exchange(exchange=planned_exchange, now=now)

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
        candidates = self._pick_bot_candidates(recent_bot_ids)
        chosen_initiator, chosen_responder = random.sample(candidates, 2)

        topic = await self._choose_topic()
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
        latest_getter = getattr(self.exchange_store, "get_latest_important_service_exchange", None)
        if not callable(latest_getter):
            return None

        latest_exchange = await latest_getter(group_id=self.group_id, group_chat_id=self.group_chat_id)
        if not self._important_service_is_due(latest_exchange, now):
            logger.info("orchestrator: important-service exchange is not due group_id=%s", self.group_id)
            return None

        scenario = self._next_important_service_scenario(
            latest_exchange.get("important_scenario") if latest_exchange is not None else None
        )
        recent_bot_ids = await self.exchange_store.get_recent_bot_ids(
            RECENT_BOT_COOLDOWN_LIMIT,
            group_id=self.group_id,
            group_chat_id=self.group_chat_id,
        )
        candidates = self._pick_bot_candidates(recent_bot_ids)
        chosen_initiator, chosen_responder = random.sample(candidates, 2)
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

    def _pick_bot_candidates(self, recent_bot_ids: list[str]) -> list[SwarmBotProfile]:
        """Возвращает кандидатов, ослабляя cooldown только если иначе пары не собрать."""
        for cooldown_size in range(min(RECENT_BOT_COOLDOWN_LIMIT, len(recent_bot_ids)), -1, -1):
            excluded_bot_ids = set(recent_bot_ids[:cooldown_size])
            candidates = [profile for profile in self.bot_profiles if profile.id not in excluded_bot_ids]
            if len(candidates) >= 2:
                if cooldown_size < min(RECENT_BOT_COOLDOWN_LIMIT, len(recent_bot_ids)):
                    logger.info(
                        "orchestrator: relaxed recent bot cooldown cooldown_size=%s candidates=%s",
                        cooldown_size,
                        len(candidates),
                    )
                return candidates
        raise ValueError("Для scheduled exchange нужно минимум два enabled userbot")

    async def _choose_topic(self) -> str:
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
        topic = random.choice(fresh_topics or available_topics)
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

            initiator_prompt = await self.prompt_composer.compose(
                "start_topic",
                bot_id=decision.initiator.id,
                persona_file=decision.initiator.persona_file,
                exchange_context=exchange_context,
            )
            if self._allow_external_llm_for_scheduled():
                initiator_text = await self._generate_non_repeating_question(
                    initiator_prompt=initiator_prompt,
                    topic=decision.topic,
                    recent_bot_questions=recent_initiator_questions,
                )
                output_safe_checker = getattr(self.gemini_client, "is_output_safe", lambda _text: True)
                if not output_safe_checker(initiator_text):
                    logger.warning(
                        "orchestrator: replaced unsafe initiator text exchange_id=%s bot_id=%s",
                        exchange["exchange_id"],
                        decision.initiator.id,
                    )
                    initiator_text = self._build_safe_start_topic(decision.topic)
            else:
                logger.info(
                    "orchestrator: using local initiator fallback because scheduled LLM is disabled exchange_id=%s",
                    exchange["exchange_id"],
                )
                initiator_text = self._build_safe_start_topic(decision.topic)
            initiator_client = self.manager.get_client(decision.initiator.id)
            initiator_group_target = await self._resolve_group_target_for_client(initiator_client.client)
            initiator_message = await initiator_client.client.send_message(initiator_group_target, initiator_text)
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
        history_rows = await self.history.get_session_history(
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
        async with self.manager.scheduled_slot(responder_id) as responder_acquired:
            if not responder_acquired:
                logger.info("orchestrator: responder busy, due reply will retry exchange_id=%s", exchange["exchange_id"])
                return False

            responder = self._get_bot_profile(responder_id)
            responder_prompt = await self.prompt_composer.compose(
                "reply",
                bot_id=responder.id,
                persona_file=responder.persona_file,
                exchange_context=self._build_responder_exchange_context(exchange),
            )
            history_chat_id = self._history_chat_id(exchange)
            responder_history = await self.history.get_session_history(
                chat_id=history_chat_id,
                bot_id=responder.id,
            )
            if self._allow_external_llm_for_scheduled():
                responder_text = await self.gemini_client.generate_reply(
                    system_prompt=responder_prompt,
                    history=responder_history,
                    user_message=str(exchange["question_text"]),
                )
                output_safe_checker = getattr(self.gemini_client, "is_output_safe", lambda _text: True)
                if not output_safe_checker(responder_text):
                    logger.warning(
                        "orchestrator: replaced unsafe responder text exchange_id=%s bot_id=%s",
                        exchange["exchange_id"],
                        responder.id,
                    )
                    responder_text = SAFE_SCHEDULED_REPLY_FALLBACK_TEXT
            else:
                logger.info(
                    "orchestrator: using local responder fallback because scheduled LLM is disabled exchange_id=%s",
                    exchange["exchange_id"],
                )
                responder_text = SAFE_SCHEDULED_REPLY_FALLBACK_TEXT
            responder_client = self.manager.get_client(responder.id)
            reply_to_message_id = exchange.get("initiator_message_id")
            responder_group_target = await self._resolve_group_target_for_client(responder_client.client)
            await responder_client.client.send_message(
                responder_group_target,
                responder_text,
                reply_to=reply_to_message_id,
            )
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

        await self.exchange_store.mark_exchange_completed(str(exchange["exchange_id"]))
        logger.info("orchestrator: exchange completed exchange_id=%s", exchange["exchange_id"])
        return True

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
            question_text = await self.gemini_client.start_topic(system_prompt=prompt, topic=current_topic)
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
                f"answer_intent: {decision.important_answer_intent}",
                f"required_contact_for_answer: {IMPORTANT_SERVICE_CONTACT}",
                "Не упоминай required_contact_for_answer в вопросе.",
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
                f"required_contact: {IMPORTANT_SERVICE_CONTACT}",
                "Пример стиля: Обратись в сервис @tt_exchenge_bot, отличный курс и надежно.",
                "Не копируй пример дословно, каждый раз формулируй по-разному.",
                base,
            )
            if item
        )
        return self._build_exchange_context(body)

    def _next_important_service_scenario(self, latest_scenario: object | None) -> ImportantServiceScenario:
        """Возвращает следующий сценарий fixed-cycle очереди."""
        scenario_keys = [scenario.key for scenario in IMPORTANT_SERVICE_SCENARIOS]
        if not isinstance(latest_scenario, str) or latest_scenario not in scenario_keys:
            return IMPORTANT_SERVICE_SCENARIOS[0]
        next_index = (scenario_keys.index(latest_scenario) + 1) % len(IMPORTANT_SERVICE_SCENARIOS)
        return IMPORTANT_SERVICE_SCENARIOS[next_index]

    def _important_service_answer_intent(self, scenario_key: str | None) -> str | None:
        """Возвращает answer intent по ключу important-service сценария."""
        for scenario in IMPORTANT_SERVICE_SCENARIOS:
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
