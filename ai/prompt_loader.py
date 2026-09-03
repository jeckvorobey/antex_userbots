"""Асинхронная загрузка runtime-промтов из Markdown-файлов."""

import logging
from pathlib import Path

from ai.text_file_cache import AsyncTextFileCache


logger = logging.getLogger(__name__)


class PromptLoader:
    """Загружает промты из настроенной директории через файловый кэш."""

    def __init__(self, prompts_dir: str, file_cache: AsyncTextFileCache | None = None) -> None:
        self.prompts_dir = prompts_dir
        self.file_cache = file_cache or AsyncTextFileCache()

    async def load(self, name: str) -> str:
        """Возвращает полное содержимое файла ``<name>.md``."""
        normalized_name = self._validate_name(name)
        path = Path(self.prompts_dir) / f"{normalized_name}.md"
        logger.info("Загрузка промта '%s' из %s", normalized_name, path)
        try:
            return await self.file_cache.read(path)
        except FileNotFoundError:
            logger.error("Файл промта не найден: %s", path)
            raise FileNotFoundError(path)

    @staticmethod
    def _validate_name(name: str) -> str:
        """Разрешает только одно непустое имя файла внутри prompts_dir."""
        normalized = name.strip()
        path = Path(normalized)
        if normalized == "" or path.is_absolute() or len(path.parts) != 1 or normalized in {".", ".."}:
            raise ValueError("prompt name должен быть именем файла внутри prompts_dir")
        return normalized
