"""Общее асинхронное подключение к SQLite для runtime."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import aiosqlite


logger = logging.getLogger(__name__)

T = TypeVar("T")


class SQLiteDatabase:
    """Владеет единым SQLite-соединением и сериализует операции записи."""

    RETRY_DELAYS = (0.2, 0.5, 1.0, 2.0)
    LOCK_ERRORS = ("database is locked", "database table is locked")

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.write_lock = asyncio.Lock()
        self._connection: aiosqlite.Connection | None = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """Возвращает открытое общее соединение."""
        if self._connection is None:
            raise RuntimeError("SQLite-соединение ещё не открыто")
        return self._connection

    async def open(self) -> None:
        """Открывает и настраивает единственное SQLite-соединение."""
        if self._connection is not None:
            return
        self._ensure_parent_dir()
        logger.info("Открытие общего SQLite-соединения: %s", self.db_path)
        self._connection = await aiosqlite.connect(self.db_path, timeout=30)
        self._connection.row_factory = aiosqlite.Row

        async def configure(connection: aiosqlite.Connection) -> None:
            await connection.execute("PRAGMA journal_mode=WAL")
            await connection.execute("PRAGMA synchronous=NORMAL")
            await connection.execute("PRAGMA busy_timeout=30000")
            await connection.execute("PRAGMA foreign_keys=ON")

        try:
            self._restrict_file_permissions()
            await self.write("configure_connection", configure)
        except BaseException:
            await self.close()
            raise

    async def write(
        self,
        operation: str,
        callback: Callable[[aiosqlite.Connection], Awaitable[T]],
    ) -> T:
        """Выполняет запись и commit под общим lock с retry блокировок."""
        async with self.write_lock:
            result = await self._retry_locked(operation, callback)
            self._restrict_file_permissions()
            return result

    async def execute(
        self,
        operation: str,
        sql: str,
        parameters: tuple[object, ...] = (),
    ) -> int:
        """Выполняет один изменяющий SQL-запрос и возвращает rowcount."""
        async def execute_statement(connection: aiosqlite.Connection) -> int:
            cursor = await connection.execute(sql, parameters)
            return int(cursor.rowcount or 0)

        return await self.write(operation, execute_statement)

    async def read(
        self,
        callback: Callable[[aiosqlite.Connection], Awaitable[T]],
    ) -> T:
        """Выполняет чтение без пересечения с незавершённой write-транзакцией."""
        async with self.write_lock:
            return await callback(self.connection)

    async def fetch_one(
        self,
        operation: str,
        sql: str,
        parameters: tuple[object, ...] = (),
    ) -> aiosqlite.Row | tuple[Any, ...] | None:
        """Возвращает одну строку под общим transaction lock."""
        async def fetch(connection: aiosqlite.Connection):
            async with connection.execute(sql, parameters) as cursor:
                return await cursor.fetchone()

        return await self.read(fetch)

    async def fetch_all(
        self,
        operation: str,
        sql: str,
        parameters: tuple[object, ...] = (),
    ) -> list[aiosqlite.Row] | list[tuple[Any, ...]]:
        """Возвращает строки под общим transaction lock."""
        async def fetch(connection: aiosqlite.Connection):
            async with connection.execute(sql, parameters) as cursor:
                return await cursor.fetchall()

        return await self.read(fetch)

    async def close(self) -> None:
        """Закрывает общее соединение не более одного раза."""
        connection = self._connection
        if connection is None:
            return
        self._connection = None
        await connection.close()

    async def _retry_locked(
        self,
        operation: str,
        callback: Callable[[aiosqlite.Connection], Awaitable[T]],
    ) -> T:
        connection = self.connection
        max_attempts = len(self.RETRY_DELAYS) + 1
        for attempt in range(1, max_attempts + 1):
            try:
                result = await callback(connection)
                await connection.commit()
                return result
            except aiosqlite.OperationalError as exc:
                await connection.rollback()
                if not self._is_lock_error(exc) or attempt == max_attempts:
                    raise
                delay = self.RETRY_DELAYS[attempt - 1]
                logger.warning(
                    "SQLite временно заблокирована: attempt=%s/%s delay=%ss operation=%s",
                    attempt + 1,
                    max_attempts,
                    delay,
                    operation,
                )
                await asyncio.sleep(delay)
            except BaseException:
                await connection.rollback()
                raise
        raise AssertionError("Недостижимая ветка retry SQLite")

    @classmethod
    def _is_lock_error(cls, exc: aiosqlite.OperationalError) -> bool:
        message = str(exc).lower()
        return any(marker in message for marker in cls.LOCK_ERRORS)

    def _ensure_parent_dir(self) -> None:
        if self.db_path == ":memory:":
            return
        parent = Path(self.db_path).parent
        if str(parent) and str(parent) != ".":
            parent.mkdir(parents=True, exist_ok=True)

    def _restrict_file_permissions(self) -> None:
        """Ограничивает доступ к SQLite-файлам владельцем процесса."""
        if self.db_path == ":memory:" or self.db_path.startswith("file:"):
            return
        database_path = Path(self.db_path)
        for path in (database_path, database_path.with_name(f"{database_path.name}-wal"), database_path.with_name(f"{database_path.name}-shm")):
            if path.exists():
                path.chmod(0o600)
