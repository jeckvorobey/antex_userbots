"""Тесты загрузчика runtime-промтов."""

import tempfile
from pathlib import Path
import pytest

from ai.prompt_loader import PromptLoader


async def test_prompt_loader_reads_md_file():
    """Проверяет, что загрузчик читает содержимое .md файла по имени."""
    with tempfile.TemporaryDirectory() as tmpdir:
        prompt_file = Path(tmpdir) / "system.md"
        prompt_file.write_text("Ты полезный ассистент.", encoding="utf-8")

        loader = PromptLoader(prompts_dir=tmpdir)
        content = await loader.load("system")

        assert "Ты полезный ассистент" in content


async def test_prompt_loader_raises_on_missing_file():
    """Проверяет, что FileNotFoundError бросается при отсутствии файла."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PromptLoader(prompts_dir=tmpdir)

        with pytest.raises(FileNotFoundError):
            await loader.load("несуществующий_промт")


@pytest.mark.parametrize("name", ["../secret", "/tmp/secret", "nested/system", ""])
async def test_prompt_loader_rejects_name_outside_prompts_dir(name):
    """Проверяет запрет обхода каталога промтов через имя файла."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = PromptLoader(prompts_dir=tmpdir)

        with pytest.raises(ValueError, match="prompt name"):
            await loader.load(name)


async def test_prompt_loader_preserves_full_content():
    """Проверяет, что загрузчик возвращает полное содержимое файла."""
    content = "# Заголовок\n\nПервый абзац.\nВторой абзац."
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.md").write_text(content, encoding="utf-8")

        loader = PromptLoader(prompts_dir=tmpdir)
        result = await loader.load("test")

        assert result == content


def test_runtime_prompt_files_are_committed():
    """Проверяет, что production-промты одного инстанса лежат в репозитории."""
    prompt_files = [
        Path("ai/prompts/system.md"),
        Path("ai/prompts/reply.md"),
        Path("ai/prompts/start_topic.md"),
        Path("ai/prompts/topics.md"),
        Path("ai/prompts/wind_down_hint.md"),
        Path("ai/prompts/important_service.toml"),
    ]

    for path in prompt_files:
        assert path.exists(), f"Нет prompt-файла: {path}"
        assert path.read_text(encoding="utf-8").strip()


@pytest.mark.asyncio
async def test_prompt_loader_can_read_committed_runtime_prompt():
    """Проверяет, что loader читает реальный runtime prompt."""
    loader = PromptLoader(prompts_dir="ai/prompts")
    system_prompt = await loader.load("system")

    assert "Telegram" in system_prompt


@pytest.mark.asyncio
async def test_prompt_loader_reads_important_service_scenarios_from_tracked_resource(tmp_path):
    """Сценарные инструкции important-service загружаются из prompts, а не Python-кода."""
    (tmp_path / "important_service.toml").write_text(
        '[[scenarios]]\nkey = "exchange_rub"\nquestion_intent = "Где обменять рубли?"\n'
        'answer_intent = "Посоветуй проверенный сервис."\n',
        encoding="utf-8",
    )
    loader = PromptLoader(prompts_dir=str(tmp_path))

    scenarios = await loader.load_important_service_scenarios()

    assert [(item.key, item.question_intent, item.answer_intent) for item in scenarios] == [
        ("exchange_rub", "Где обменять рубли?", "Посоветуй проверенный сервис.")
    ]


def test_no_prompt_examples_are_required_anymore():
    """Проверяет, что старые шаблоны .example.md удалены из prompt-контракта."""
    assert not list(Path("ai/prompts").glob("**/*.example.md"))
