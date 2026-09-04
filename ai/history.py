"""Модуль хранения истории диалогов в SQLite через aiosqlite."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import aiosqlite

from storage.sqlite_database import SQLiteDatabase


logger = logging.getLogger(__name__)


def _to_utc_sqlite_timestamp(value: datetime) -> str:
    """Приводит datetime к UTC-строке в формате SQLite."""
    if value.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo or UTC
        value = value.replace(tzinfo=local_tz)
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


class MessageHistory:
    """Хранит историю сообщений каждого пользователя в SQLite базе данных."""

    def __init__(self, database: SQLiteDatabase) -> None:
        """
        Инициализирует хранилище истории.

        Args:
            database: Общее открытое SQLite-подключение runtime.
        """
        self.database = database

    async def init_db(self) -> None:
        """Создаёт таблицу messages в базе данных, если она не существует."""
        logger.info("Инициализация базы истории сообщений")
        async def initialize(connection: aiosqlite.Connection) -> None:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER,
                    bot_id TEXT,
                    exchange_id TEXT,
                    message_origin TEXT,
                    reply_to_message_id INTEGER,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await self._ensure_column(connection, "chat_id", "INTEGER")
            await self._ensure_column(connection, "bot_id", "TEXT")
            await self._ensure_column(connection, "exchange_id", "TEXT")
            await self._ensure_column(connection, "message_origin", "TEXT")
            await self._ensure_column(connection, "reply_to_message_id", "INTEGER")
            await self._ensure_column(connection, "created_at", "TIMESTAMP")
            await self._ensure_indexes(connection)

        await self.database.write("init_message_history", initialize)
        logger.info("Таблица истории сообщений готова")

    async def save_message(
        self,
        user_id: int,
        role: str,
        text: str,
        chat_id: int | None = None,
        bot_id: str | None = None,
        exchange_id: str | None = None,
        message_origin: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> None:
        """
        Сохраняет сообщение в историю диалога.

        Args:
            user_id: Telegram ID пользователя.
            role: Роль отправителя — 'user' или 'assistant'.
            text: Текст сообщения.
            chat_id: Telegram ID чата (группы).
        """
        logger.info(
            "Сохранение сообщения в историю для user_id=%s, role=%s, длина=%s",
            user_id,
            role,
            len(text),
        )
        created_at = _to_utc_sqlite_timestamp(datetime.now(UTC))
        async def save(connection: aiosqlite.Connection) -> None:
            await connection.execute(
                """
                INSERT INTO messages (
                    user_id, chat_id, bot_id, exchange_id, message_origin,
                    reply_to_message_id, role, text, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, chat_id, bot_id, exchange_id, message_origin,
                    reply_to_message_id, role, text, created_at,
                ),
            )

        await self.database.write("save_message", save)
        logger.info("Сообщение сохранено в историю для user_id=%s", user_id)

    async def get_history(
        self, user_id: int, limit: int = 20
    ) -> list[dict[str, Any]]:
        """
        Возвращает историю сообщений для указанного пользователя.

        Args:
            user_id: Telegram ID пользователя.
            limit: Максимальное количество возвращаемых сообщений (от новых к старым).

        Returns:
            Список словарей с ключами 'role' и 'text', упорядоченных по времени.
        """
        logger.info("Загрузка истории сообщений для user_id=%s с limit=%s", user_id, limit)
        rows = await self.database.fetch_all(
            "get_user_history",
            """
            SELECT role, text
            FROM (
                SELECT role, text, id
                FROM messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
            ) recent_messages
            ORDER BY id ASC
            """,
            (user_id, limit),
        )
        messages = [{"role": row[0], "text": row[1]} for row in rows]
        logger.info("Загружена история сообщений для user_id=%s: %s записей", user_id, len(messages))
        return messages

    async def get_session_history(
        self,
        chat_id: int | None,
        session_start: datetime | None = None,
        limit: int = 50,
        bot_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Возвращает историю сообщений всех участников чата за текущую сессию.

        Args:
            chat_id: Telegram ID чата. Если None — возвращает пустой список.
            session_start: Начало сессии; если задано, фильтрует сообщения по времени.
            limit: Максимальное количество возвращаемых сообщений.

        Returns:
            Список словарей с ключами 'role' и 'text', упорядоченных по времени.
        """
        if chat_id is None:
            return []

        logger.info(
            "Загрузка истории сессии для chat_id=%s, session_start=%s, limit=%s",
            chat_id,
            session_start,
            limit,
        )
        params: list[Any] = [chat_id]
        where_parts = ["chat_id = ?"]
        if bot_id is not None:
            where_parts.append("bot_id = ?")
            params.append(bot_id)

        if session_start is not None:
            session_start_str = _to_utc_sqlite_timestamp(session_start)
            params.append(session_start_str)
            params.append(limit)
            rows = await self.database.fetch_all(
                "get_session_history_since",
                f"""
                SELECT role, text, bot_id, exchange_id, message_origin, reply_to_message_id
                FROM messages
                WHERE {' AND '.join(where_parts)} AND created_at >= ?
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                tuple(params),
            )
        else:
            params.append(limit)
            rows = await self.database.fetch_all(
                "get_session_history",
                f"""
                SELECT role, text, bot_id, exchange_id, message_origin, reply_to_message_id FROM (
                    SELECT role, text, bot_id, exchange_id, message_origin, reply_to_message_id, id FROM messages
                    WHERE {' AND '.join(where_parts)}
                    ORDER BY id DESC
                    LIMIT ?
                ) sub
                ORDER BY id ASC
                """,
                tuple(params),
            )

        messages = [
            {
                "role": row[0],
                "text": row[1],
                "bot_id": row[2],
                "exchange_id": row[3],
                "message_origin": row[4],
                "reply_to_message_id": row[5],
            }
            for row in rows
        ]
        logger.info(
            "Загружена история сессии для chat_id=%s: %s записей", chat_id, len(messages)
        )
        return messages

    async def prune_older_than(self, *, retention_days: int) -> int:
        """Удаляет старые сообщения по retention window."""
        if retention_days <= 0:
            logger.info("Пропуск очистки history: retention_days=%s", retention_days)
            return 0

        cutoff = _to_utc_sqlite_timestamp(datetime.now(UTC) - timedelta(days=retention_days))
        async def prune(connection: aiosqlite.Connection) -> int:
            cursor = await connection.execute(
                "DELETE FROM messages WHERE created_at < ?",
                (cutoff,),
            )
            return int(cursor.rowcount or 0)

        deleted = await self.database.write("prune_message_history", prune)
        logger.info("Очистка history завершена: retention_days=%s deleted=%s", retention_days, deleted)
        return deleted

    async def _ensure_column(self, connection: aiosqlite.Connection, column_name: str, column_type: str) -> None:
        """Добавляет колонку в messages; пропускает только duplicate-column."""
        try:
            await connection.execute(f"ALTER TABLE messages ADD COLUMN {column_name} {column_type}")
        except aiosqlite.OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise

    async def _ensure_indexes(self, connection: aiosqlite.Connection) -> None:
        """Создаёт индексы для горячих запросов истории."""
        index_statements = [
            """
            CREATE INDEX IF NOT EXISTS idx_messages_user_id_id
            ON messages (user_id, id DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_id_id
            ON messages (chat_id, id DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_bot_id
            ON messages (chat_id, bot_id, id DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_created_at
            ON messages (chat_id, created_at, id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_bot_created_at
            ON messages (chat_id, bot_id, created_at, id)
            """,
        ]
        for statement in index_statements:
            await connection.execute(statement)
