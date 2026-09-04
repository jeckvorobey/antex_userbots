"""Асинхронная загрузка runtime-промтов из Markdown-файлов."""

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ai.text_file_cache import AsyncTextFileCache


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ImportantServiceScenario:
    """Проверенный сценарий important-service из prompt-ресурса."""

    key: str
    question_intent: str
    answer_intent: str


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

    async def load_important_service_scenarios(self) -> tuple[ImportantServiceScenario, ...]:
        """Загружает и валидирует сценарии important-service из TOML-ресурса."""
        path = Path(self.prompts_dir) / "important_service.toml"
        logger.info("Загрузка important-service сценариев из %s", path)
        content = await self.file_cache.read(path)
        try:
            raw_scenarios = tomllib.loads(content).get("scenarios")
        except tomllib.TOMLDecodeError as exc:
            raise ValueError("Некорректный important_service.toml") from exc
        if not isinstance(raw_scenarios, list) or not raw_scenarios:
            raise ValueError("important_service.toml должен содержать непустой список scenarios")

        scenarios: list[ImportantServiceScenario] = []
        seen_keys: set[str] = set()
        for raw in raw_scenarios:
            if not isinstance(raw, dict):
                raise ValueError("Каждый important-service scenario должен быть таблицей")
            values = {name: raw.get(name) for name in ("key", "question_intent", "answer_intent")}
            if any(not isinstance(value, str) or not value.strip() for value in values.values()):
                raise ValueError("Important-service scenario требует key, question_intent и answer_intent")
            key = values["key"].strip()
            if key in seen_keys:
                raise ValueError(f"Повторяющийся important-service scenario key: {key}")
            seen_keys.add(key)
            scenarios.append(
                ImportantServiceScenario(
                    key=key,
                    question_intent=values["question_intent"].strip(),
                    answer_intent=values["answer_intent"].strip(),
                )
            )
        return tuple(scenarios)

    @staticmethod
    def _validate_name(name: str) -> str:
        """Разрешает только одно непустое имя файла внутри prompts_dir."""
        normalized = name.strip()
        path = Path(normalized)
        if normalized == "" or path.is_absolute() or len(path.parts) != 1 or normalized in {".", ".."}:
            raise ValueError("prompt name должен быть именем файла внутри prompts_dir")
        return normalized
