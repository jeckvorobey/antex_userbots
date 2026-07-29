"""Асинхронный кэш текстовых файлов с обновлением при изменении на диске."""

from __future__ import annotations

import asyncio
from pathlib import Path


class AsyncTextFileCache:
    """Кэширует текст, сохраняя файловые операции вне event loop."""

    def __init__(self) -> None:
        self._entries: dict[Path, tuple[int, int, str]] = {}

    async def read(self, path: Path) -> str:
        """Возвращает текст файла и обновляет кэш при смене mtime или размера."""
        return await asyncio.to_thread(self._read_sync, path)

    def _read_sync(self, path: Path) -> str:
        resolved_path = path.resolve()
        stat = resolved_path.stat()
        cached = self._entries.get(resolved_path)
        signature = (stat.st_mtime_ns, stat.st_size)
        if cached is not None and cached[:2] == signature:
            return cached[2]

        content = resolved_path.read_text(encoding="utf-8")
        self._entries[resolved_path] = (*signature, content)
        return content
