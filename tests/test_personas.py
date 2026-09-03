"""Проверки production-промтов, тем и persona-файлов."""

from pathlib import Path

import pytest

def _prod_persona_files() -> set[str]:
    """Возвращает persona-файлы, объявленные в production TOML."""
    import tomllib

    settings_path = Path("config/settings.prod.toml")
    if not settings_path.exists():
        pytest.skip("Локальный config/settings.prod.toml отсутствует в этом checkout")
    settings_data = tomllib.loads(settings_path.read_text(encoding="utf-8"))
    return {
        bot["persona_file"]
        for bot in settings_data["swarm"]["bots"]
    }


def test_prod_persona_inventory_matches_settings():
    """Проверяет, что committed persona inventory соответствует production settings."""
    configured_personas = _prod_persona_files()
    committed_personas = {
        path.name
        for path in Path("ai/prompts/bots").glob("*.md")
    }

    assert committed_personas == configured_personas


def test_prod_personas_are_detailed_and_structured():
    """Проверяет, что production persona-профили достаточно подробные и структурированные."""
    required_sections = [
        "## Характер",
        "## Манера общения",
        "## Поведение в чате",
        "## Поведение в групповых обсуждениях",
        "## Реакции",
        "## Стиль мышления",
        "## Интересы",
        "## Небольшой жизненный контекст",
        "## Индивидуальные привычки",
        "## Поведение в конфликте",
        "## Ограничения",
        "## Вероятностное поведение",
        "## Взаимоотношения",
        "## Человеческие несовершенства",
    ]

    for persona_file in _prod_persona_files():
        text = (Path("ai/prompts/bots") / persona_file).read_text(encoding="utf-8")

        assert len(text.split()) >= 300, f"Persona слишком короткая: {persona_file}"
        for section in required_sections:
            assert section in text, f"В {persona_file} нет секции {section}"
        assert "никогда не сообщает, что он AI" in text or "никогда не сообщает, что она AI" in text
        assert "не копирует стиль других персонажей" in text
        assert "не превращается в \"идеального помощника\"" in text


def test_prod_personas_are_not_duplicate_templates():
    """Проверяет, что production persona-профили не являются одинаковыми шаблонами."""
    persona_texts = {
        persona_file: (Path("ai/prompts/bots") / persona_file).read_text(encoding="utf-8")
        for persona_file in _prod_persona_files()
    }
    unique_texts = set(persona_texts.values())

    assert len(unique_texts) == len(persona_texts)


def test_shared_topics_are_city_neutral_intents():
    """Проверяет, что общий topics.md не содержит готовые вопросы под один город."""
    topics_path = Path("ai/prompts/topics.md")
    city_markers = {"нячанг", "danang", "da nang", "батум", "batumi"}
    topic_lines = [
        line.strip()
        for line in topics_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#") and line.strip() != "---"
    ]

    assert topic_lines
    assert all("?" not in line for line in topic_lines)
    lowered = "\n".join(topic_lines).lower()
    assert not any(marker in lowered for marker in city_markers)


def test_start_topic_prompt_requires_city_adaptation():
    """Проверяет, что start_topic prompt адаптирует общий intent под город группы."""
    prompt = Path("ai/prompts/start_topic.md").read_text(encoding="utf-8").lower()

    assert "город" in prompt
    assert "не упоминай другой город" in prompt
    assert "не копируй тему дословно" in prompt


def test_start_topic_prompt_defines_human_opening_rule():
    """Проверяет, что общий start_topic prompt задаёт человеческие варианты начала."""
    prompt = Path("ai/prompts/start_topic.md").read_text(encoding="utf-8").lower()

    assert '"привет"' in prompt
    assert '"всем привет"' in prompt
    assert '"здравствуйте"' in prompt
    assert "без вступительного слова" in prompt
    assert "сразу задавай вопрос" in prompt


def test_important_service_start_topic_prompt_contract():
    """Проверяет prompt-контракт important-service вопроса."""
    prompt = Path("ai/prompts/start_topic.md").read_text(encoding="utf-8")

    assert "important_service_question" in prompt
    assert "question_intent" in prompt
    assert "не упоминай `https://t.me/tt_exchenge_bot/antex`" in prompt
    assert "отсутствует, не добавляй рекламный смысл" in prompt


def test_important_service_reply_prompt_contract():
    """Проверяет prompt-контракт important-service ответа."""
    prompt = Path("ai/prompts/reply.md").read_text(encoding="utf-8")

    assert "important_service_answer" in prompt
    assert "естественно упомяни miniapp-ссылку `https://t.me/tt_exchenge_bot/antex`" in prompt
    assert "каждый раз меняй формулировку" in prompt
    assert "отсутствует, не упоминай `https://t.me/tt_exchenge_bot/antex` специально" in prompt


def test_prod_persona_communication_style_avoids_marker_openers():
    """Проверяет, что манера общения не закрепляет заметные стартовые маркеры."""
    marker_openers = ["кстати", "слушай", "слушайте", "смотри"]
    human_opening_patterns = [
        "сразу",
        "прямо",
        "привет",
        "без вступления",
        "без лишнего захода",
    ]

    for persona_file in _prod_persona_files():
        text = (Path("ai/prompts/bots") / persona_file).read_text(encoding="utf-8")
        communication_style = text.split("## Манера общения", maxsplit=1)[1].split("## ", maxsplit=1)[0].lower()
        restrictions = text.split("## Ограничения", maxsplit=1)[1].split("## ", maxsplit=1)[0].lower()

        assert "не начинает сообщения" not in restrictions, persona_file
        for opener in marker_openers:
            assert opener not in communication_style, persona_file
        assert any(pattern in communication_style for pattern in human_opening_patterns), persona_file
