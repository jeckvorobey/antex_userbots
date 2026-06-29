"""SQLite-хранилище scheduled exchange и persisted state orchestrator."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite


logger = logging.getLogger(__name__)


def normalize_signature(value: str) -> str:
    """Нормализует текст для дедупликации тем и вопросов."""
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    normalized = re.sub(r"[^\w\s]+", "", normalized)
    return normalized.strip()


class ExchangeStore:
    """Хранит exchange, их статусы и persisted state для anti-repeat."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def init_db(self) -> None:
        """Создаёт таблицу scheduled_exchanges, если она ещё не существует."""
        connection = await self._get_connection()
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_exchanges (
                exchange_id TEXT PRIMARY KEY,
                initiator_bot_id TEXT NOT NULL,
                responder_bot_id TEXT NOT NULL,
                pair_key TEXT NOT NULL,
                window_key TEXT,
                topic TEXT NOT NULL,
                topic_key TEXT NOT NULL,
                question_text TEXT,
                question_signature TEXT,
                initiator_scheduled_at TIMESTAMP,
                responder_scheduled_at TIMESTAMP,
                initiator_message_id INTEGER,
                status TEXT NOT NULL DEFAULT 'planned',
                skip_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
            """
        )
        await connection.commit()
        await self._ensure_column(connection, "pair_key", "TEXT")
        await self._ensure_column(connection, "window_key", "TEXT")
        await self._ensure_column(connection, "topic_key", "TEXT")
        await self._ensure_column(connection, "question_text", "TEXT")
        await self._ensure_column(connection, "question_signature", "TEXT")
        await self._ensure_column(connection, "initiator_scheduled_at", "TIMESTAMP")
        await self._ensure_column(connection, "responder_scheduled_at", "TIMESTAMP")
        await self._ensure_column(connection, "initiator_message_id", "INTEGER")
        await self._ensure_column(connection, "skip_reason", "TEXT")
        await self._ensure_column(connection, "started_at", "TIMESTAMP")
        await self._ensure_column(connection, "completed_at", "TIMESTAMP")
        logger.info("Таблица scheduled_exchanges готова")

    async def create_exchange(
        self,
        *,
        initiator_bot_id: str,
        responder_bot_id: str,
        topic: str,
        topic_key: str | None = None,
        window_key: str | None = None,
        initiator_scheduled_at: datetime | None = None,
    ) -> str:
        """Создаёт запись planned exchange и возвращает её идентификатор."""
        exchange_id = str(uuid.uuid4())
        normalized_topic_key = topic_key or normalize_signature(topic)
        pair_key = self.build_pair_key(initiator_bot_id, responder_bot_id)
        connection = await self._get_connection()
        await connection.execute(
            """
            INSERT INTO scheduled_exchanges (
                exchange_id,
                initiator_bot_id,
                responder_bot_id,
                pair_key,
                window_key,
                topic,
                topic_key,
                initiator_scheduled_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'planned')
            """,
            (
                exchange_id,
                initiator_bot_id,
                responder_bot_id,
                pair_key,
                window_key,
                topic,
                normalized_topic_key,
                self._serialize_timestamp(initiator_scheduled_at),
            ),
        )
        await connection.commit()
        logger.info(
            "Создан planned exchange: exchange_id=%s initiator=%s responder=%s topic_key=%s window_key=%s initiator_due=%s",
            exchange_id,
            initiator_bot_id,
            responder_bot_id,
            normalized_topic_key,
            window_key,
            self._serialize_timestamp(initiator_scheduled_at),
        )
        return exchange_id

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
        connection = await self._get_connection()
        await connection.execute(
            """
            UPDATE scheduled_exchanges
            SET status = 'started',
                initiator_message_id = ?,
                question_text = ?,
                question_signature = ?,
                responder_scheduled_at = ?,
                started_at = CURRENT_TIMESTAMP
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
        await connection.commit()
        logger.info("Exchange помечен как started: exchange_id=%s", exchange_id)

    async def mark_exchange_completed(self, exchange_id: str) -> None:
        """Помечает exchange как завершённый."""
        connection = await self._get_connection()
        await connection.execute(
            """
            UPDATE scheduled_exchanges
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP
            WHERE exchange_id = ?
            """,
            (exchange_id,),
        )
        await connection.commit()
        logger.info("Exchange помечен как completed: exchange_id=%s", exchange_id)

    async def get_recent_bot_ids(self, limit: int) -> list[str]:
        """Возвращает последние уникальные bot_id, которые писали scheduled-сообщения."""
        if limit <= 0:
            return []
        connection = await self._get_connection()
        async with connection.execute(
            """
            SELECT bot_id
            FROM (
                SELECT
                    initiator_bot_id AS bot_id,
                    COALESCE(started_at, created_at) AS event_at,
                    rowid AS exchange_rowid,
                    0 AS event_order
                FROM scheduled_exchanges
                WHERE status IN ('started', 'completed')
                  AND started_at IS NOT NULL

                UNION ALL

                SELECT
                    responder_bot_id AS bot_id,
                    COALESCE(completed_at, started_at, created_at) AS event_at,
                    rowid AS exchange_rowid,
                    1 AS event_order
                FROM scheduled_exchanges
                WHERE status = 'completed'
                  AND completed_at IS NOT NULL
            ) bot_events
            ORDER BY datetime(event_at) DESC, exchange_rowid DESC, event_order DESC
            """,
        ) as cursor:
            rows = await cursor.fetchall()

        recent_bot_ids: list[str] = []
        seen_bot_ids: set[str] = set()
        for row in rows:
            bot_id = row[0]
            if not isinstance(bot_id, str) or bot_id in seen_bot_ids:
                continue
            recent_bot_ids.append(bot_id)
            seen_bot_ids.add(bot_id)
            if len(recent_bot_ids) >= limit:
                break

        logger.info("Загружены последние scheduled bot_id: count=%s", len(recent_bot_ids))
        return recent_bot_ids

    async def get_exchange_by_window_key(self, window_key: str) -> dict[str, object] | None:
        """Возвращает exchange, уже зарегистрированный в текущем окне."""
        connection = await self._get_connection()
        async with connection.execute(
            """
            SELECT *
            FROM scheduled_exchanges
            WHERE window_key = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (window_key,),
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row is not None else None

    async def get_due_started_exchange(self, *, now: datetime) -> dict[str, object] | None:
        """Возвращает ближайший started exchange, которому пора отправить ответ."""
        connection = await self._get_connection()
        async with connection.execute(
            """
            SELECT *
            FROM scheduled_exchanges
            WHERE status = 'started'
              AND responder_scheduled_at IS NOT NULL
              AND datetime(responder_scheduled_at) <= datetime(?)
            ORDER BY datetime(responder_scheduled_at) ASC, started_at ASC
            LIMIT 1
            """,
            (self._serialize_timestamp(now),),
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row is not None else None

    async def get_recent_topic_keys_by_limit(self, limit: int) -> set[str]:
        """Возвращает topic_key из последних started/completed exchange."""
        if limit <= 0:
            return set()
        connection = await self._get_connection()
        async with connection.execute(
            """
            SELECT topic_key
            FROM scheduled_exchanges
            WHERE status IN ('started', 'completed')
            ORDER BY datetime(COALESCE(started_at, created_at)) DESC, rowid DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        topic_keys = {row[0] for row in rows if isinstance(row[0], str)}
        logger.info("Загружены последние topic_key по limit=%s: count=%s", limit, len(topic_keys))
        return topic_keys

    async def get_recent_question_signatures(self, *, since: timedelta) -> set[str]:
        """Возвращает сигнатуры недавно использованных вопросов."""
        threshold = self._threshold_timestamp(since)
        connection = await self._get_connection()
        async with connection.execute(
            """
            SELECT DISTINCT question_signature
            FROM scheduled_exchanges
            WHERE question_signature IS NOT NULL
              AND status IN ('started', 'completed')
              AND datetime(COALESCE(started_at, created_at)) >= datetime(?)
            """,
            (threshold,),
        ) as cursor:
            rows = await cursor.fetchall()
        signatures = {row[0] for row in rows if isinstance(row[0], str)}
        logger.info("Загружены recent question_signature: count=%s since=%s", len(signatures), threshold)
        return signatures

    async def get_recent_questions(self, *, since: timedelta, limit: int = 10) -> list[str]:
        """Возвращает последние вопросы для prompt context."""
        threshold = self._threshold_timestamp(since)
        connection = await self._get_connection()
        async with connection.execute(
            """
            SELECT COALESCE(question_text, topic)
            FROM scheduled_exchanges
            WHERE status IN ('started', 'completed')
              AND datetime(COALESCE(started_at, created_at)) >= datetime(?)
            ORDER BY COALESCE(started_at, created_at) DESC
            LIMIT ?
            """,
            (threshold, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        questions = [row[0] for row in rows if isinstance(row[0], str)]
        logger.info("Загружены recent questions для контекста: count=%s", len(questions))
        return questions

    async def close(self) -> None:
        """Закрывает SQLite-соединение."""
        if self._connection is None:
            return
        await self._connection.close()
        self._connection = None

    async def _get_connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            self._ensure_parent_dir()
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
        return self._connection

    def _ensure_parent_dir(self) -> None:
        """Создаёт директорию для файловой SQLite базы."""
        if self.db_path == ":memory:":
            return
        parent = Path(self.db_path).parent
        if str(parent) and str(parent) != ".":
            parent.mkdir(parents=True, exist_ok=True)

    async def _ensure_column(self, connection: aiosqlite.Connection, column_name: str, column_type: str) -> None:
        """Добавляет колонку, если её ещё нет; пропускает только duplicate-column."""
        try:
            await connection.execute(f"ALTER TABLE scheduled_exchanges ADD COLUMN {column_name} {column_type}")
            await connection.commit()
        except aiosqlite.OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise

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
