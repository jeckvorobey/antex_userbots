"""Тесты TOML-конфигурации приложения."""

from pathlib import Path
from unittest.mock import patch

import pytest

from core.config import Settings, SettingsReloadWatcher


BASE_SECRETS = {
    "api_id": 12345678,
    "api_hash": "test_api_hash_abc",
    "gemini_api_key": "test_gemini_key_xyz",
    "group_chat_id": -100123,
    "group_target": "@group",
}


def write_settings(tmp_path: Path, content: str) -> Path:
    """Создаёт временный settings.toml для теста."""
    path = tmp_path / "settings.toml"
    path.write_text(content.strip(), encoding="utf-8")
    return path


def test_settings_loads_non_secret_values_from_toml(tmp_path):
    """Проверяет загрузку несекретных параметров из TOML."""
    settings_path = write_settings(
        tmp_path,
        """
        [app]
        mode = "swarm"

        [storage]
        db_path = ":memory:"

        [prompts]
        base_dir = "custom/prompts"
        topics_path = "custom/topics.md"
        bot_profiles_dir = "custom/bots"

        [gemini]
        model = "gemini-test"
        fallback_model = "gemini-lite"
        temperature = 1.2
        max_retries = 4
        retry_backoff_seconds = 2.0
        retry_jitter_seconds = 0.4
        request_timeout_seconds = 12.5

        [logging]
        level = "DEBUG"
        """,
    )

    settings = Settings(**BASE_SECRETS, settings_path=str(settings_path))

    assert settings.mode == "swarm"
    assert settings.db_path == ":memory:"
    assert settings.topics_path == "custom/topics.md"
    assert settings.prompts_dir == "custom/prompts"
    assert settings.bot_profiles_dir == "custom/bots"
    assert settings.gemini_model == "gemini-test"
    assert settings.gemini_fallback_model == "gemini-lite"
    assert settings.gemini_temperature == 1.2
    assert settings.gemini_max_retries == 4
    assert settings.group_chat_id == -100123
    assert settings.group_target == "@group"
    assert settings.log_level == "DEBUG"


def test_settings_with_secret_overrides_ignores_local_toml_without_settings_path(tmp_path, monkeypatch):
    """Проверяет изоляцию тестовых overrides от локального settings.toml."""
    write_settings(
        tmp_path,
        """
        [gemini]
        model = "gemini-local-toml"
        """,
    )
    monkeypatch.chdir(tmp_path)

    settings = Settings(**BASE_SECRETS)

    assert settings.gemini_model == "gemini-2.5-flash"


def test_settings_path_can_come_from_env(tmp_path):
    """Проверяет, что SETTINGS_PATH выбирает TOML-файл."""
    settings_path = write_settings(
        tmp_path,
        """
        [app]
        mode = "swarm"

        [gemini]
        model = "gemini-from-env"
        """,
    )
    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        settings = Settings(_env_file=None)

    assert settings.mode == "swarm"
    assert settings.gemini_model == "gemini-from-env"


def test_settings_rejects_group_target_in_toml(tmp_path):
    """Проверяет, что Telegram-цель больше не читается из TOML."""
    settings_path = write_settings(
        tmp_path,
        """
        [telegram]
        group_chat_id = -100123
        group_target = "@group"
        """,
    )

    with pytest.raises(Exception):
        Settings(**BASE_SECRETS, settings_path=str(settings_path))


def test_settings_rejects_target_section_from_toml(tmp_path):
    """Проверяет, что [target] больше не входит в публичный TOML-контракт."""
    settings_path = write_settings(
        tmp_path,
        """
        [app]
        mode = "swarm"

        [target]
        group_chat_id = -100987654321
        group_target = "@swarm_group"

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"

        [[swarm.bots]]
        id = "mike"
        session_env = "SESSION_STRING_MIKE"
        persona_file = "mike.md"
        """,
    )

    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SESSION_STRING_MIKE": "mike-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(Exception, match="target"):
            Settings(_env_file=None)


def test_settings_reads_multi_group_config_and_schedule_overrides(tmp_path):
    """Проверяет загрузку нескольких групп и наследование расписания."""
    settings_path = write_settings(
        tmp_path,
        """
        [app]
        mode = "swarm"

        [swarm.schedule]
        active_windows_utc = ["10-12"]
        initiator_offset_minutes = [1, 2]
        responder_delay_minutes = [3, 4]
        max_turns_per_exchange = 2

        [[groups]]
        id = "danang"
        city = "Da Nang"
        enabled = true
        group_chat_id = -100111
        group_target = "@danang_chat"

        [[groups]]
        id = "batumi"
        city = "Batumi"
        enabled = false
        group_chat_id = -100222

        [groups.schedule]
        active_windows_utc = ["14-16"]
        responder_delay_minutes = [8, 9]

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        settings = Settings(_env_file=None)

    assert [group.id for group in settings.groups] == ["danang", "batumi"]
    assert [group.id for group in settings.enabled_groups] == ["danang"]
    assert settings.groups[0].active_windows_utc == ["10-12"]
    assert settings.groups[0].responder_delay_minutes == (3, 4)
    assert settings.groups[1].active_windows_utc == ["14-16"]
    assert settings.groups[1].initiator_offset_minutes == (1, 2)
    assert settings.groups[1].responder_delay_minutes == (8, 9)


def test_settings_rejects_duplicate_group_ids(tmp_path):
    """Проверяет запрет дублирующихся group.id."""
    settings_path = write_settings(
        tmp_path,
        """
        [[groups]]
        id = "danang"
        city = "Da Nang"
        group_chat_id = -100111

        [[groups]]
        id = "DANANG"
        city = "Da Nang 2"
        group_target = "@danang2"

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(Exception, match="group id"):
            Settings(_env_file=None)


def test_settings_rejects_group_without_target(tmp_path):
    """Проверяет, что группа без id чата и target невалидна."""
    settings_path = write_settings(
        tmp_path,
        """
        [[groups]]
        id = "danang"
        city = "Da Nang"

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(Exception, match="group_chat_id|group_target"):
            Settings(_env_file=None)


def test_settings_reload_watcher_returns_new_settings_on_mtime_change(tmp_path):
    """Проверяет non-mutating reload по mtime settings.toml."""
    settings_path = write_settings(
        tmp_path,
        """
        [[groups]]
        id = "danang"
        city = "Da Nang"
        group_chat_id = -100111
        """,
    )
    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        settings = Settings(_env_file=None)
        watcher = SettingsReloadWatcher(settings)
        assert watcher.poll() is None
        settings_path.write_text(
            """
            [[groups]]
            id = "danang"
            city = "Da Nang"
            group_chat_id = -100111

            [[groups]]
            id = "batumi"
            city = "Batumi"
            group_chat_id = -100222
            """.strip(),
            encoding="utf-8",
        )
        reloaded = watcher.poll()

    assert reloaded is not None
    assert reloaded is not settings
    assert [group.id for group in reloaded.groups] == ["danang", "batumi"]


def test_settings_rejects_missing_explicit_settings_path(tmp_path):
    """Проверяет ошибку при отсутствующем явно переданном TOML-файле."""
    missing_path = tmp_path / "missing-settings.toml"

    with pytest.raises(FileNotFoundError, match="Файл настроек не найден"):
        Settings(**BASE_SECRETS, settings_path=str(missing_path))


def test_settings_rejects_missing_settings_path_from_env(tmp_path):
    """Проверяет ошибку при отсутствующем SETTINGS_PATH из окружения."""
    missing_path = tmp_path / "missing-settings.toml"
    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SETTINGS_PATH": str(missing_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(FileNotFoundError, match="Файл настроек не найден"):
            Settings(_env_file=None)


def test_settings_rejects_missing_settings_path_from_env_file(tmp_path):
    """Проверяет ошибку при отсутствующем SETTINGS_PATH из .env."""
    missing_path = tmp_path / "missing-settings.toml"
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "API_ID=12345678",
                "API_HASH=test_hash",
                "GEMINI_API_KEY=test_key",
                f"SETTINGS_PATH={missing_path}",
            ],
        ),
        encoding="utf-8",
    )

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(FileNotFoundError, match="Файл настроек не найден"):
            Settings(_env_file=str(env_path))


def test_settings_reads_swarm_sessions_from_env_file(tmp_path):
    """Проверяет загрузку SESSION_STRING_* из .env-файла без экспорта в shell."""
    settings_path = write_settings(
        tmp_path,
        """
        [app]
        mode = "swarm"

        [[swarm.bots]]
        id = "sofia"
        session_env = "SESSION_STRING_SOFIA"
        persona_file = "sofia.md"
        """,
    )
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "API_ID=12345678",
                "API_HASH=test_hash",
                "GEMINI_API_KEY=test_key",
                "SESSION_STRING_SOFIA=sofia-session",
                f"SETTINGS_PATH={settings_path}",
            ],
        ),
        encoding="utf-8",
    )

    with patch.dict("os.environ", {}, clear=True):
        settings = Settings(_env_file=str(env_path))

    assert settings.swarm_bot_ids == ["sofia"]
    assert settings.swarm_bots[0].session_string == "sofia-session"


def test_settings_loads_swarm_mode_and_bots(tmp_path):
    """Проверяет загрузку swarm-режима и списка ботов из TOML."""
    settings_path = write_settings(
        tmp_path,
        """
        [app]
        mode = "swarm"

        [storage]
        db_path = ":memory:"

        [prompts]
        base_dir = "custom/prompts"
        topics_path = "custom/topics.md"
        bot_profiles_dir = "custom/bots"

        [swarm.schedule]
        active_windows_utc = ["10-11", "16-18"]
        initiator_offset_minutes = [0, 30]
        responder_delay_minutes = [3, 10]
        max_turns_per_exchange = 2

        [swarm.orchestrator]
        tick_seconds = 30
        silence_timeout_minutes = 60
        skip_if_recent_human_activity = true

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        enabled = true
        temperature = 0.9

        [[swarm.bots]]
        id = "mike"
        session_env = "SESSION_STRING_MIKE"
        persona_file = "mike.md"
        enabled = false
        temperature = 0.8
        """,
    )

    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SESSION_STRING_MIKE": "mike-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        settings = Settings(_env_file=None)

    assert settings.mode == "swarm"
    assert settings.db_path == ":memory:"
    assert settings.prompts_dir == "custom/prompts"
    assert settings.topics_path == "custom/topics.md"
    assert settings.swarm_schedule_active_windows_utc == ["10-11", "16-18"]
    assert settings.swarm_initiator_offset_minutes == (0, 30)
    assert settings.swarm_responder_delay_minutes == (3, 10)
    assert settings.swarm_max_turns_per_exchange == 2
    assert settings.swarm_tick_seconds == 30
    assert settings.swarm_silence_timeout_minutes == 60
    assert settings.swarm_skip_if_recent_human_activity is True
    assert settings.swarm_bot_ids == ["anna", "mike"]
    assert settings.swarm_bots[0].session_string == "anna-session"
    assert settings.swarm_bots[1].session_string == "mike-session"


@pytest.mark.parametrize(
    "window_value",
    ['["10-10"]', '["10"]', '["10-25"]'],
)
def test_settings_rejects_invalid_active_windows(tmp_path, window_value: str):
    """Проверяет валидацию некорректных UTC-окон в swarm.schedule."""
    settings_path = write_settings(
        tmp_path,
        f"""
        [app]
        mode = "swarm"

        [swarm.schedule]
        active_windows_utc = {window_value}

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(Exception):
            Settings(_env_file=None)


@pytest.mark.parametrize("value", ["[-1, 5]", "[5, 4]"])
def test_settings_rejects_invalid_minute_ranges(tmp_path, value: str):
    """Проверяет валидацию некорректных диапазонов минут в swarm.schedule."""
    settings_path = write_settings(
        tmp_path,
        f"""
        [app]
        mode = "swarm"

        [swarm.schedule]
        responder_delay_minutes = {value}

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(Exception):
            Settings(_env_file=None)


def test_settings_rejects_duplicate_swarm_bot_ids(tmp_path):
    """Проверяет запрет дублирующихся bot.id в swarm-конфигурации."""
    settings_path = write_settings(
        tmp_path,
        """
        [app]
        mode = "swarm"

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA_2"
        persona_file = "anna-2.md"
        """,
    )

    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SESSION_STRING_ANNA_2": "anna-session-2",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(Exception, match="bot id"):
            Settings(_env_file=None)


def test_settings_rejects_missing_swarm_session_env(tmp_path):
    """Проверяет ошибку, если session_env бота не найден в окружении."""
    settings_path = write_settings(
        tmp_path,
        """
        [app]
        mode = "swarm"

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(Exception, match="SESSION_STRING_ANNA"):
            Settings(_env_file=None)


@pytest.mark.parametrize(
    ("toml_fragment", "key_name"),
    [
        ("[paths]\nreply_" + "rules_path = \"custom/rules.md\"", "paths"),
        ("[telegram]\nwhite" + "list_user_ids = [111, 222]", "telegram"),
        ("[swarm]\nenabled = true", "enabled"),
        ("[swarm]\nmax_parallel_bots = 12", "max_parallel_bots"),
        ("[swarm]\nignore_messages_from_swarm = true", "ignore_messages_from_swarm"),
        ("[swarm]\nreply_only_to_addressed_bot = true", "reply_only_to_addressed_bot"),
        ("[swarm.schedule]\npair_" + "cooldown_slots = 1", "pair_" + "cooldown_slots"),
    ],
)
def test_settings_rejects_removed_toml_keys(tmp_path, toml_fragment: str, key_name: str):
    """Проверяет строгий отказ от удалённых legacy TOML-ключей."""
    settings_path = write_settings(
        tmp_path,
        f"""
        [app]
        mode = "swarm"

        {toml_fragment}

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(Exception, match=key_name):
            Settings(_env_file=None)


@pytest.mark.parametrize("persona_file", ["../secret.md", "/tmp/secret.md"])
def test_settings_rejects_persona_file_outside_profiles_dir(tmp_path, persona_file: str):
    """Проверяет запрет path traversal в persona_file."""
    settings_path = write_settings(
        tmp_path,
        f"""
        [app]
        mode = "swarm"

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "{persona_file}"
        """,
    )

    env = {
        "API_ID": "12345678",
        "API_HASH": "test_hash",
        "GEMINI_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(Exception, match="persona_file"):
            Settings(_env_file=None)
