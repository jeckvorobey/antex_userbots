"""Тесты асинхронного кэша текстовых файлов."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ai.text_file_cache import AsyncTextFileCache


@pytest.mark.asyncio
async def test_text_file_cache_reuses_unchanged_content(tmp_path, monkeypatch):
    """Проверяет отсутствие повторного чтения неизменённого файла."""
    path = tmp_path / "prompt.md"
    path.write_text("Первая версия", encoding="utf-8")
    original_read_text = Path.read_text
    read_count = 0

    def read_text(self, **kwargs):
        nonlocal read_count
        read_count += 1
        return original_read_text(self, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    cache = AsyncTextFileCache()

    first = await cache.read(path)
    second = await cache.read(path)

    assert first == second == "Первая версия"
    assert read_count == 1


@pytest.mark.asyncio
async def test_text_file_cache_refreshes_changed_file(tmp_path):
    """Проверяет обновление кэша после изменения файла."""
    path = tmp_path / "prompt.md"
    path.write_text("v1", encoding="utf-8")
    cache = AsyncTextFileCache()

    assert await cache.read(path) == "v1"
    path.write_text("version two", encoding="utf-8")

    assert await cache.read(path) == "version two"


@pytest.mark.asyncio
async def test_text_file_cache_raises_for_missing_file(tmp_path):
    """Проверяет сохранение FileNotFoundError для обязательных файлов."""
    cache = AsyncTextFileCache()

    with pytest.raises(FileNotFoundError):
        await cache.read(tmp_path / "missing.md")


@pytest.mark.asyncio
async def test_text_file_cache_delegates_file_io_to_thread(tmp_path, monkeypatch):
    """Проверяет вынос файловых операций из event loop."""
    path = tmp_path / "prompt.md"
    path.write_text("text", encoding="utf-8")
    to_thread = AsyncMock(return_value="text")
    monkeypatch.setattr("ai.text_file_cache.asyncio.to_thread", to_thread)
    cache = AsyncTextFileCache()

    assert await cache.read(path) == "text"
    to_thread.assert_awaited_once_with(cache._read_sync, path)
