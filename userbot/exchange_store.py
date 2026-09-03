"""SQLite-хранилище scheduled exchange и persisted state orchestrator."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

import aiosqlite

from storage.sqlite_database import SQLiteDatabase


logger = logging.getLogger(__name__)


def _redact_quarantine_group_key(group_key: str) -> str:
    """Скрывает private Telegram invite из audit-лога quarantine."""
    normalized = group_key.strip().lower()
    if "t.me/+" in normalized or "t.me/joinchat/" in normalized:
        return "<private invite link>"
    return group_key


def normalize_signature(value: str) -> str:
    """Нормализует текст для дедупликации тем и вопросов."""
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    normalized = re.sub(r"[^\w\s]+", "", normalized)
    return normalized.strip()


class ExchangeStore:
    """Хранит exchange, их статусы и persisted state для anti-repeat."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    async def init_db(self) -> None:
        """Создаёт таблицу scheduled_exchanges, если она ещё не существует."""
        async def initialize(connection: aiosqlite.Connection) -> None:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_exchanges (
                exchange_id TEXT PRIMARY KEY,
                group_id TEXT,
                group_chat_id INTEGER,
                initiator_bot_id TEXT NOT NULL,
                responder_bot_id TEXT NOT NULL,
                pair_key TEXT NOT NULL,
                window_key TEXT,
                topic TEXT NOT NULL,
                topic_key TEXT NOT NULL,
                question_text TEXT,
                question_signature TEXT,
                responder_text TEXT,
                initiator_scheduled_at TIMESTAMP,
                responder_scheduled_at TIMESTAMP,
                initiator_message_id INTEGER,
                exchange_kind TEXT NOT NULL DEFAULT 'regular',
                important_scenario TEXT,
                status TEXT NOT NULL DEFAULT 'planned',
                skip_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await connection.execute(
                """CREATE TABLE IF NOT EXISTS quarantined_swarm_bots (
                    group_key TEXT NOT NULL,
                    bot_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (group_key, bot_id)
                )"""
            )
            for column_name, column_type in (("is_available", "INTEGER"), ("checked_at", "TIMESTAMP")):
                try:
                    await connection.execute(f"ALTER TABLE quarantined_swarm_bots ADD COLUMN {column_name} {column_type}")
                except Exception as exc:
                    if "duplicate column name" not in str(exc).lower():
                        raise
            await self._ensure_column(connection, "group_id", "TEXT")
            await self._ensure_column(connection, "group_chat_id", "INTEGER")
            await self._ensure_column(connection, "pair_key", "TEXT")
            await self._ensure_column(connection, "window_key", "TEXT")
            await self._ensure_column(connection, "topic_key", "TEXT")
            await self._ensure_column(connection, "question_text", "TEXT")
            await self._ensure_column(connection, "question_signature", "TEXT")
            await self._ensure_column(connection, "responder_text", "TEXT")
            await self._ensure_column(connection, "initiator_scheduled_at", "TIMESTAMP")
            await self._ensure_column(connection, "responder_scheduled_at", "TIMESTAMP")
            await self._ensure_column(connection, "initiator_message_id", "INTEGER")
            await self._ensure_column(connection, "exchange_kind", "TEXT NOT NULL DEFAULT 'regular'")
            await self._ensure_column(connection, "important_scenario", "TEXT")
            await self._ensure_column(connection, "skip_reason", "TEXT")
            await self._ensure_column(connection, "created_at", "TIMESTAMP")
            await self._ensure_column(connection, "started_at", "TIMESTAMP")
            await self._ensure_column(connection, "completed_at", "TIMESTAMP")
            await self._ensure_column(connection, "last_activity_at", "TIMESTAMP")
            await self._backfill_last_activity_at(connection)
            await self._ensure_indexes(connection)

        await self.database.write("init_exchange_store", initialize)
        logger.info("Таблица scheduled_exchanges готова")

    async def quarantine_bot(self, *, group_key: str, bot_id: str, reason: str) -> None:
        """Сохраняет запрет на автоматическое использование аккаунта."""
        await self.database.execute(
            "quarantine_bot",
            """INSERT INTO quarantined_swarm_bots (group_key, bot_id, reason)
               VALUES (?, ?, ?)
               ON CONFLICT(group_key, bot_id) DO UPDATE SET reason = excluded.reason, quarantined_at = CURRENT_TIMESTAMP""",
            (group_key, bot_id, reason),
        )
        logger.error(
            "swarm quarantine persisted: bot_id=%s group_key=%s reason=%s auto_reuse=false",
            bot_id,
            _redact_quarantine_group_key(group_key),
            reason,
        )

    async def reset_startup_availability(self) -> None:
        """Очищает прошлый startup-снимок доступности ботов."""
        await self.database.execute(
            "reset_startup_availability",
            "DELETE FROM quarantined_swarm_bots WHERE group_key = '__startup__'",
        )

    async def record_startup_availability(self, *, bot_id: str, is_available: bool, reason: str | None) -> None:
        """Сохраняет свежий итог startup-проверки без секретных данных."""
        await self.database.execute(
            "record_startup_availability",
            """INSERT INTO quarantined_swarm_bots (group_key, bot_id, reason, is_available, checked_at)
               VALUES ('__startup__', ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(group_key, bot_id) DO UPDATE SET reason=excluded.reason,
                   is_available=excluded.is_available, checked_at=excluded.checked_at""",
            (bot_id, reason or "", int(is_available)),
        )

    async def get_quarantined_bot_ids(self) -> set[str]:
        """Возвращает аккаунты, которые нельзя автоматически запускать после рестарта."""
        rows = await self.database.fetch_all(
            "get_quarantined_bot_ids",
            "SELECT DISTINCT bot_id FROM quarantined_swarm_bots WHERE group_key != '__startup__'",
        )
        return {str(row[0]) for row in rows}

    async def create_exchange(
        self,
        *,
        initiator_bot_id: str,
        responder_bot_id: str,
        topic: str,
        group_id: str | None = None,
        group_chat_id: int | None = None,
        topic_key: str | None = None,
        window_key: str | None = None,
        initiator_scheduled_at: datetime | None = None,
        exchange_kind: str = "regular",
        important_scenario: str | None = None,
    ) -> str:
        """Создаёт запись planned exchange и возвращает её идентификатор."""
        exchange_id = str(uuid.uuid4())
        normalized_topic_key = topic_key or normalize_signature(topic)
        pair_key = self.build_pair_key(initiator_bot_id, responder_bot_id)
        await self.database.execute(
            "create_exchange",
            """
            INSERT INTO scheduled_exchanges (
                exchange_id,
                group_id,
                group_chat_id,
                initiator_bot_id,
                responder_bot_id,
                pair_key,
                window_key,
                topic,
                topic_key,
                initiator_scheduled_at,
                exchange_kind,
                important_scenario,
                last_activity_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'planned')
            """,
            (
                exchange_id,
                group_id,
                group_chat_id,
                initiator_bot_id,
                responder_bot_id,
                pair_key,
                window_key,
                topic,
                normalized_topic_key,
                self._serialize_timestamp(initiator_scheduled_at),
                exchange_kind,
                important_scenario,
            ),
        )
        logger.info(
            "Создан planned exchange: exchange_id=%s group_id=%s group_chat_id=%s initiator=%s responder=%s topic_key=%s window_key=%s kind=%s important_scenario=%s initiator_due=%s",
            exchange_id,
            group_id,
            group_chat_id,
            initiator_bot_id,
            responder_bot_id,
            normalized_topic_key,
            window_key,
            exchange_kind,
            important_scenario,
            self._serialize_timestamp(initiator_scheduled_at),
        )
        return exchange_id

    async def get_exchange(self, exchange_id: str) -> dict[str, object] | None:
        """Возвращает exchange по идентификатору."""
        row = await self.database.fetch_one(
            "get_exchange",
            """
            SELECT *
            FROM scheduled_exchanges
            WHERE exchange_id = ?
            LIMIT 1
            """,
            (exchange_id,),
        )
        return dict(row) if row is not None else None

    async def mark_initiator_generated(self, exchange_id: str, *, question_text: str, question_signature: str | None = None) -> None:
        """Сохраняет вопрос до сетевой отправки Telegram."""
        await self.database.execute(
            "mark_initiator_generated",
            """UPDATE scheduled_exchanges
               SET question_text = ?, question_signature = ?, last_activity_at = CURRENT_TIMESTAMP
               WHERE exchange_id = ?""",
            (question_text, normalize_signature(question_signature or question_text), exchange_id),
        )

    async def mark_responder_generated(self, exchange_id: str, responder_text: str) -> None:
        """Сохраняет ответ до сетевой отправки Telegram."""
        await self.database.execute(
            "mark_responder_generated",
            """UPDATE scheduled_exchanges
               SET responder_text = ?, last_activity_at = CURRENT_TIMESTAMP
               WHERE exchange_id = ?""",
            (responder_text, exchange_id),
        )

    async def reassign_after_permanent_send_error(
        self, exchange_id: str, *, stage: str, replacement_bot_id: str, counterpart_bot_id: str
    ) -> None:
        """Переназначает неотправленный turn на другую персону."""
        if stage == "initiator":
            sql = """UPDATE scheduled_exchanges
                     SET initiator_bot_id = ?, pair_key = ?, question_text = NULL,
                         question_signature = NULL, last_activity_at = CURRENT_TIMESTAMP
                     WHERE exchange_id = ?"""
            params = (replacement_bot_id, self.build_pair_key(replacement_bot_id, counterpart_bot_id), exchange_id)
        elif stage == "responder":
            sql = """UPDATE scheduled_exchanges
                     SET responder_bot_id = ?, pair_key = ?, responder_text = NULL,
                         last_activity_at = CURRENT_TIMESTAMP
                     WHERE exchange_id = ?"""
            params = (replacement_bot_id, self.build_pair_key(counterpart_bot_id, replacement_bot_id), exchange_id)
        else:
            raise ValueError(f"Unsupported exchange stage: {stage}")
        await self.database.execute("reassign_after_permanent_send_error", sql, params)

    async def mark_exchange_started(
        self,
        exchange_id: str,
        *,
        initiator_message_id: int | None = None,
        question_text: str | None = None,
        question_signature: str | None = None,
        responder_scheduled_at: datetime | None = None,
    ) -> None:
        """Помечает exchange как начатый."""
        await self.database.execute(
            "mark_exchange_started",
            """
            UPDATE scheduled_exchanges
            SET status = 'started',
                initiator_message_id = ?,
                question_text = ?,
                question_signature = ?,
                responder_scheduled_at = ?,
                started_at = CURRENT_TIMESTAMP,
                last_activity_at = CURRENT_TIMESTAMP
            WHERE exchange_id = ?
            """,
            (
                initiator_message_id,
                question_text,
                normalize_signature(question_signature) if question_signature else None,
                self._serialize_timestamp(responder_scheduled_at),
                exchange_id,
            ),
        )
        logger.info("Exchange помечен как started: exchange_id=%s", exchange_id)

    async def mark_exchange_completed(self, exchange_id: str) -> None:
        """Помечает exchange как завершённый."""
        await self.database.execute(
            "mark_exchange_completed",
            """
            UPDATE scheduled_exchanges
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP,
                last_activity_at = CURRENT_TIMESTAMP
            WHERE exchange_id = ?
            """,
            (exchange_id,),
        )
        logger.info("Exchange помечен как completed: exchange_id=%s", exchange_id)

    async def get_recent_bot_ids(self, limit: int, *, group_id: str | None = None, group_chat_id: int | None = None) -> list[str]:
        """Возвращает последние уникальные bot_id, которые писали scheduled-сообщения."""
        if limit <= 0:
            return []
        filter_sql, filter_params = self._build_group_filter(group_id=group_id, group_chat_id=group_chat_id)
        rows = await self.database.fetch_all(
            "get_recent_bot_ids",
            f"""
            WITH bot_events AS (
                SELECT
                    initiator_bot_id AS bot_id,
                    COALESCE(started_at, created_at) AS event_at,
                    rowid AS exchange_rowid,
                    0 AS event_order
                FROM scheduled_exchanges
                WHERE status IN ('started', 'completed')
                  AND started_at IS NOT NULL
                  {filter_sql}

                UNION ALL

                SELECT
                    responder_bot_id AS bot_id,
                    COALESCE(completed_at, started_at, created_at) AS event_at,
                    rowid AS exchange_rowid,
                    1 AS event_order
                FROM scheduled_exchanges
                WHERE status = 'completed'
                  AND completed_at IS NOT NULL
                  {filter_sql}
            ),
            latest_bot_events AS (
                SELECT bot_id, event_at, exchange_rowid, event_order
                FROM (
                    SELECT
                        bot_id,
                        event_at,
                        exchange_rowid,
                        event_order,
                        ROW_NUMBER() OVER (
                            PARTITION BY bot_id
                            ORDER BY event_at DESC, exchange_rowid DESC, event_order DESC
                        ) AS bot_rank
                    FROM bot_events
                )
                WHERE bot_rank = 1
            )
            SELECT bot_id
            FROM latest_bot_events
            ORDER BY event_at DESC, exchange_rowid DESC, event_order DESC
            LIMIT ?
            """,
            (*filter_params, *filter_params, limit),
        )

        recent_bot_ids = [row[0] for row in rows if isinstance(row[0], str)]

        logger.info("Загружены последние scheduled bot_id: count=%s", len(recent_bot_ids))
        return recent_bot_ids

    async def get_exchange_by_window_key(
        self,
        window_key: str,
        *,
        group_id: str | None = None,
        group_chat_id: int | None = None,
    ) -> dict[str, object] | None:
        """Возвращает exchange, уже зарегистрированный в текущем окне."""
        filter_sql, filter_params = self._build_group_filter(group_id=group_id, group_chat_id=group_chat_id)
        row = await self.database.fetch_one(
            "get_exchange_by_window_key",
            f"""
            SELECT *
            FROM scheduled_exchanges
            WHERE window_key = ?
              {filter_sql}
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (window_key, *filter_params),
        )
        return dict(row) if row is not None else None

    async def get_due_started_exchange(
        self,
        *,
        now: datetime,
        group_id: str | None = None,
        group_chat_id: int | None = None,
    ) -> dict[str, object] | None:
        """Возвращает ближайший started exchange, которому пора отправить ответ."""
        filter_sql, filter_params = self._build_group_filter(group_id=group_id, group_chat_id=group_chat_id)
        row = await self.database.fetch_one(
            "get_due_started_exchange",
            f"""
            SELECT *
            FROM scheduled_exchanges
            WHERE status = 'started'
              AND responder_scheduled_at IS NOT NULL
              AND responder_scheduled_at <= ?
              {filter_sql}
            ORDER BY responder_scheduled_at ASC, started_at ASC
            LIMIT 1
            """,
            (self._serialize_timestamp(now), *filter_params),
        )
        return dict(row) if row is not None else None

    async def get_recent_topic_keys_by_limit(
        self,
        limit: int,
        *,
        group_id: str | None = None,
        group_chat_id: int | None = None,
    ) -> set[str]:
        """Возвращает topic_key из последних started/completed exchange."""
        if limit <= 0:
            return set()
        filter_sql, filter_params = self._build_group_filter(group_id=group_id, group_chat_id=group_chat_id)
        rows = await self.database.fetch_all(
            "get_recent_topic_keys",
            f"""
            SELECT topic_key
            FROM scheduled_exchanges
            WHERE status IN ('started', 'completed')
              {filter_sql}
            ORDER BY last_activity_at DESC, rowid DESC
            LIMIT ?
            """,
            (*filter_params, limit),
        )
        topic_keys = {row[0] for row in rows if isinstance(row[0], str)}
        logger.info("Загружены последние topic_key по limit=%s: count=%s", limit, len(topic_keys))
        return topic_keys

    async def get_recent_question_signatures(
        self,
        *,
        since: timedelta,
        group_id: str | None = None,
        group_chat_id: int | None = None,
    ) -> set[str]:
        """Возвращает сигнатуры недавно использованных вопросов."""
        threshold = self._threshold_timestamp(since)
        filter_sql, filter_params = self._build_group_filter(group_id=group_id, group_chat_id=group_chat_id)
        rows = await self.database.fetch_all(
            "get_recent_question_signatures",
            f"""
            SELECT DISTINCT question_signature
            FROM scheduled_exchanges
            WHERE question_signature IS NOT NULL
              AND status IN ('started', 'completed')
              AND last_activity_at >= ?
              {filter_sql}
            """,
            (threshold, *filter_params),
        )
        signatures = {row[0] for row in rows if isinstance(row[0], str)}
        logger.info("Загружены recent question_signature: count=%s since=%s", len(signatures), threshold)
        return signatures

    async def get_recent_questions(
        self,
        *,
        since: timedelta,
        limit: int = 10,
        group_id: str | None = None,
        group_chat_id: int | None = None,
    ) -> list[str]:
        """Возвращает последние вопросы для prompt context."""
        threshold = self._threshold_timestamp(since)
        filter_sql, filter_params = self._build_group_filter(group_id=group_id, group_chat_id=group_chat_id)
        rows = await self.database.fetch_all(
            "get_recent_questions",
            f"""
            SELECT COALESCE(question_text, topic)
            FROM scheduled_exchanges
            WHERE status IN ('started', 'completed')
              AND last_activity_at >= ?
              {filter_sql}
            ORDER BY last_activity_at DESC, rowid DESC
            LIMIT ?
            """,
            (threshold, *filter_params, limit),
        )
        questions = [row[0] for row in rows if isinstance(row[0], str)]
        logger.info("Загружены recent questions для контекста: count=%s", len(questions))
        return questions

    async def get_latest_important_service_exchange(
        self,
        *,
        group_id: str | None = None,
        group_chat_id: int | None = None,
    ) -> dict[str, object] | None:
        """Возвращает последний important-service exchange для группы."""
        filter_sql, filter_params = self._build_group_filter(group_id=group_id, group_chat_id=group_chat_id)
        row = await self.database.fetch_one(
            "get_latest_important_service_exchange",
            f"""
            SELECT *
            FROM scheduled_exchanges
            WHERE exchange_kind = 'important_service'
              AND status IN ('started', 'completed')
              {filter_sql}
            ORDER BY last_activity_at DESC, rowid DESC
            LIMIT 1
            """,
            filter_params,
        )
        return dict(row) if row is not None else None

    async def prune_older_than(self, *, retention_days: int) -> int:
        """Удаляет старые scheduled exchange по retention window."""
        if retention_days <= 0:
            logger.info("Пропуск очистки scheduled_exchanges: retention_days=%s", retention_days)
            return 0

        cutoff = (datetime.now(UTC) - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
        deleted = await self.database.execute(
            "prune_exchange_store",
            """
            DELETE FROM scheduled_exchanges
            WHERE COALESCE(last_activity_at, created_at) < ?
            """,
            (cutoff,),
        )
        logger.info(
            "Очистка scheduled_exchanges завершена: retention_days=%s deleted=%s",
            retention_days,
            deleted,
        )
        return deleted

    async def _ensure_column(self, connection: aiosqlite.Connection, column_name: str, column_type: str) -> None:
        """Добавляет колонку, если её ещё нет; пропускает только duplicate-column."""
        try:
            await connection.execute(f"ALTER TABLE scheduled_exchanges ADD COLUMN {column_name} {column_type}")
        except aiosqlite.OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise

    async def _backfill_last_activity_at(self, connection: aiosqlite.Connection) -> None:
        """Заполняет persisted sort key для legacy exchange rows."""
        await connection.execute(
            """
            UPDATE scheduled_exchanges
            SET last_activity_at = COALESCE(completed_at, started_at, created_at)
            WHERE last_activity_at IS NULL
              AND COALESCE(completed_at, started_at, created_at) IS NOT NULL
            """
        )

    async def _ensure_indexes(self, connection: aiosqlite.Connection) -> None:
        """Создаёт индексы для горячих запросов scheduled exchange."""
        index_statements = [
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_group_window_created
            ON scheduled_exchanges (group_id, group_chat_id, window_key, created_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_chat_window_created
            ON scheduled_exchanges (group_chat_id, window_key, created_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_group_due_responder
            ON scheduled_exchanges (group_id, group_chat_id, status, responder_scheduled_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_chat_due_responder
            ON scheduled_exchanges (group_chat_id, status, responder_scheduled_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_group_recent_started
            ON scheduled_exchanges (group_id, group_chat_id, status, started_at, created_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_chat_recent_started
            ON scheduled_exchanges (group_chat_id, status, started_at, created_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_group_recent_completed
            ON scheduled_exchanges (group_id, group_chat_id, status, completed_at, started_at, created_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_chat_recent_completed
            ON scheduled_exchanges (group_chat_id, status, completed_at, started_at, created_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_group_important_recent
            ON scheduled_exchanges (group_id, group_chat_id, exchange_kind, status, last_activity_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_chat_important_recent
            ON scheduled_exchanges (group_chat_id, exchange_kind, status, last_activity_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_group_activity_recent
            ON scheduled_exchanges (group_id, group_chat_id, status, last_activity_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_exchanges_chat_activity_recent
            ON scheduled_exchanges (group_chat_id, status, last_activity_at DESC)
            """,
        ]
        for statement in index_statements:
            await connection.execute(statement)

    @staticmethod
    def _build_group_filter(*, group_id: str | None, group_chat_id: int | None) -> tuple[str, tuple[object, ...]]:
        """Строит SQL-фильтр group scope для anti-repeat запросов."""
        clauses: list[str] = []
        params: list[object] = []
        if group_id is not None:
            clauses.append("AND group_id = ?")
            params.append(group_id)
        if group_chat_id is not None:
            clauses.append("AND group_chat_id = ?")
            params.append(group_chat_id)
        return ("\n                  " + "\n                  ".join(clauses) if clauses else "", tuple(params))

    @staticmethod
    def build_pair_key(initiator_bot_id: str, responder_bot_id: str) -> str:
        """Строит persisted ключ пары A->B."""
        return f"{initiator_bot_id}->{responder_bot_id}"

    @staticmethod
    def _threshold_timestamp(since: timedelta) -> str:
        """Возвращает UTC timestamp для SQL-фильтра recent-запросов."""
        return (datetime.now(UTC) - since).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _serialize_timestamp(value: datetime | None) -> str | None:
        """Преобразует datetime в SQLite-friendly UTC timestamp."""
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
