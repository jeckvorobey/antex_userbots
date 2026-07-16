"""Межпроцессное владение swarm runtime для container handover."""

from __future__ import annotations

import asyncio
import errno
import fcntl
import logging
import os
import stat
from pathlib import Path
from typing import IO


logger = logging.getLogger(__name__)


class RuntimeLockTimeoutError(TimeoutError):
    """Ожидание освобождения runtime lock превысило допустимый timeout."""


class RuntimeInstanceLock:
    """Удерживает эксклюзивное владение swarm для одного SQLite-файла."""

    def __init__(
        self,
        db_path: str,
        *,
        poll_interval_seconds: float = 0.5,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.db_path = db_path
        self.poll_interval_seconds = max(0.01, poll_interval_seconds)
        self.timeout_seconds = max(0.0, timeout_seconds)
        self.lock_path = None if db_path == ":memory:" else f"{db_path}.runtime.lock"
        self._handle: IO[str] | None = None
        self._acquired = False

    async def acquire(self, *, shutdown_event: asyncio.Event | None = None) -> bool:
        """Ожидает эксклюзивный lock или возвращает False при shutdown."""
        if self.lock_path is None:
            self._acquired = True
            return True
        if self._acquired:
            return True

        lock_file = Path(self.lock_path)
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        open_flags = os.O_CREAT | os.O_RDWR
        open_flags |= getattr(os, "O_CLOEXEC", 0)
        open_flags |= getattr(os, "O_NOFOLLOW", 0)
        file_descriptor = os.open(lock_file, open_flags, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
                raise OSError(errno.EINVAL, "Runtime lock должен быть обычным файлом", self.lock_path)
            os.fchmod(file_descriptor, 0o600)
            self._handle = os.fdopen(file_descriptor, "r+", encoding="utf-8")
        except BaseException:
            try:
                os.close(file_descriptor)
            except OSError:
                pass
            raise
        loop = asyncio.get_running_loop()
        started_at = loop.time()
        waiting_logged = False

        try:
            while True:
                if shutdown_event is not None and shutdown_event.is_set():
                    self.release()
                    return False
                try:
                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    elapsed = loop.time() - started_at
                    if elapsed >= self.timeout_seconds:
                        raise RuntimeLockTimeoutError(
                            f"Не удалось получить runtime lock {self.lock_path} за {self.timeout_seconds:.1f} сек"
                        )
                    if not waiting_logged:
                        logger.info(
                            "Runtime lock занят другим процессом, ожидание: path=%s timeout=%.1f sec",
                            self.lock_path,
                            self.timeout_seconds,
                        )
                        waiting_logged = True
                    if await self._wait_for_retry(shutdown_event):
                        self.release()
                        return False
                    continue

                self._acquired = True
                self._handle.seek(0)
                self._handle.truncate()
                self._handle.write(str(os.getpid()))
                self._handle.flush()
                logger.info("Runtime lock получен: path=%s", self.lock_path)
                return True
        except BaseException:
            if not self._acquired:
                self.release()
            raise

    async def _wait_for_retry(self, shutdown_event: asyncio.Event | None) -> bool:
        """Возвращает True, если shutdown получен во время polling delay."""
        if shutdown_event is None:
            await asyncio.sleep(self.poll_interval_seconds)
            return False
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=self.poll_interval_seconds)
        except TimeoutError:
            return False
        return True

    def release(self) -> None:
        """Освобождает kernel lock; сам lock-файл остаётся на volume."""
        handle = self._handle
        self._handle = None
        was_acquired = self._acquired
        self._acquired = False
        if handle is None:
            return
        try:
            if was_acquired:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
        if was_acquired:
            logger.info("Runtime lock освобождён: path=%s", self.lock_path)
