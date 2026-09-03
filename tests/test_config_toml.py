"""Тесты TOML-конфигурации приложения."""

from pathlib import Path
import tomllib
from unittest.mock import patch

import pytest

from core.config import Settings, SettingsReloadWatcher


BASE_SECRETS = {
    "openrouter_api_key": "test_openrouter_key_xyz",
    "group_chat_id": -100123,
    "group_target": "@group",
}


def write_settings(tmp_path: Path, content: str) -> Path:
    """Создаёт временный settings.toml для теста."""
    path = tmp_path / "settings.toml"
    normalized = content.strip()
    if "[telegram]" not in normalized:
        normalized = '[telegram]\napi_id = 12345678\napi_hash = "test_api_hash_abc"\n\n' + normalized
    if "[openrouter]" not in normalized and "[gemini]" not in normalized:
        normalized = '[openrouter]\nmodels = ["test/primary", "test/fallback"]\n\n' + normalized
    path.write_text(normalized, encoding="utf-8")
    return path


def write_default_settings(tmp_path: Path, content: str) -> Path:
    """Создаёт встроенный config/settings.toml для проверки default path."""
    path = tmp_path / "config" / "settings.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.strip()
    if "[telegram]" not in normalized:
        normalized = '[telegram]\napi_id = 12345678\napi_hash = "test_api_hash_abc"\n\n' + normalized
    if "[openrouter]" not in normalized and "[gemini]" not in normalized:
        normalized = '[openrouter]\nmodels = ["test/primary", "test/fallback"]\n\n' + normalized
    path.write_text(normalized, encoding="utf-8")
    return path


def test_settings_loads_non_secret_values_from_minimal_toml(tmp_path):
    """Проверяет загрузку минимального TOML-контракта и кодовых defaults."""
    settings_path = write_settings(
        tmp_path,
        """
        [[groups]]
        id = "danang"
        city = "Da Nang"
        group_chat_id = -100111

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    with patch.dict("os.environ", {"SESSION_STRING_ANNA": "anna-session"}, clear=False):
        settings = Settings(
            **BASE_SECRETS,
            settings_path=str(settings_path),
        )

    assert settings.mode == "swarm"
    assert settings.db_path == "data/history.db"
    assert settings.topics_path == "ai/prompts/topics.md"
    assert settings.prompts_dir == "ai/prompts"
    assert settings.bot_profiles_dir == "ai/prompts/bots"
    assert settings.openrouter_models == ["test/primary", "test/fallback"]
    assert settings.openrouter_temperature is None
    assert settings.api_id == 12345678
    assert settings.api_hash == "test_api_hash_abc"
    assert settings.openrouter_request_timeout_seconds == 45.0
    assert settings.group_chat_id == -100123
    assert settings.group_target == "@group"
    assert settings.log_level == "INFO"


def test_settings_uses_builtin_default_settings_path(tmp_path, monkeypatch):
    """Проверяет built-in default path config/settings.toml без SETTINGS_PATH."""
    write_default_settings(
        tmp_path,
        """
        [openrouter]
        models = ["test/default", "test/fallback"]

        [[groups]]
        id = "danang"
        city = "Da Nang"
        group_chat_id = -100111

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )
    monkeypatch.chdir(tmp_path)

    env = {
        "OPENROUTER_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
    }

    with patch.dict("os.environ", env, clear=True):
        settings = Settings(_env_file=None)

    assert settings.settings_path == "config/settings.toml"
    assert settings.openrouter_models == ["test/default", "test/fallback"]


def test_settings_path_can_come_from_env(tmp_path):
    """Проверяет, что env override SETTINGS_PATH всё ещё поддерживается."""
    settings_path = write_settings(
        tmp_path,
        """
        [openrouter]
        models = ["test/local", "test/fallback"]

        [[groups]]
        id = "danang"
        city = "Da Nang"
        group_chat_id = -100111

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )
    env = {
        "OPENROUTER_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        settings = Settings(_env_file=None)

    assert settings.mode == "swarm"
    assert settings.openrouter_models == ["test/local", "test/fallback"]


@pytest.mark.parametrize(
    "models",
    [
        '["only/one"]',
        '["one/model", " one/model "]',
        '["one/model", "   "]',
    ],
)
def test_settings_rejects_invalid_openrouter_model_lists(tmp_path, models):
    """Проверяет минимум, уникальность и непустые slug моделей."""
    settings_path = write_settings(
        tmp_path,
        f"""
        [openrouter]
        models = {models}
        """,
    )

    with pytest.raises(Exception):
        Settings(**BASE_SECRETS, settings_path=str(settings_path))


def test_settings_rejects_missing_openrouter_section(tmp_path):
    """Проверяет обязательность операторского списка моделей."""
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        '[telegram]\napi_id = 12345678\napi_hash = "test_api_hash_abc"\n\n'
        '[logging]\nlevel = "INFO"\n',
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        Settings(**BASE_SECRETS, settings_path=str(settings_path))


@pytest.mark.parametrize(
    "telegram_toml",
    [
        "",
        '[telegram]\napi_hash = "test_api_hash_abc"',
        "[telegram]\napi_id = 12345678",
    ],
)
def test_settings_requires_telegram_credentials_in_toml(tmp_path, telegram_toml):
    """Проверяет обязательность обоих Telegram credentials в TOML."""
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        f'{telegram_toml}\n\n[openrouter]\nmodels = ["test/primary", "test/fallback"]\n',
        encoding="utf-8",
    )

    with pytest.raises(Exception, match="telegram|api_id|api_hash"):
        Settings(**BASE_SECRETS, settings_path=str(settings_path))


@pytest.mark.parametrize(
    "telegram_toml",
    [
        '[telegram]\napi_id = 0\napi_hash = "test_api_hash_abc"',
        '[telegram]\napi_id = -1\napi_hash = "test_api_hash_abc"',
        '[telegram]\napi_id = 12345678\napi_hash = "   "',
    ],
)
def test_settings_rejects_invalid_telegram_credentials(tmp_path, telegram_toml):
    """Проверяет положительный api_id и непустой api_hash."""
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        f'{telegram_toml}\n\n[openrouter]\nmodels = ["test/primary", "test/fallback"]\n',
        encoding="utf-8",
    )

    with pytest.raises(Exception, match="api_id|api_hash"):
        Settings(**BASE_SECRETS, settings_path=str(settings_path))


def test_settings_rejects_legacy_gemini_section(tmp_path):
    """Проверяет удаление TOML-контракта Gemini."""
    settings_path = write_settings(
        tmp_path,
        """
        [gemini]
        model = "legacy/model"
        """,
    )

    with pytest.raises(Exception, match="gemini"):
        Settings(**BASE_SECRETS, settings_path=str(settings_path))


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
        "OPENROUTER_API_KEY": "test_key",
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
        "OPENROUTER_API_KEY": "test_key",
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


def test_settings_reads_swarm_security_section(tmp_path):
    """Проверяет загрузку security-настроек swarm из TOML."""
    settings_path = write_settings(
        tmp_path,
        """
        [swarm.security]
        allow_external_llm_for_replies = false
        allow_external_llm_for_scheduled = false
        addressed_reply_rate_limit_count = 2
        addressed_reply_rate_limit_window_seconds = 45
        addressed_reply_max_pending_per_bot = 4
        max_output_chars = 280
        max_mentions_per_message = 1
        history_retention_days = 7

        [[groups]]
        id = "danang"
        city = "Da Nang"
        group_chat_id = -100111

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    with patch.dict("os.environ", {"SESSION_STRING_ANNA": "anna-session"}, clear=False):
        settings = Settings(
            **BASE_SECRETS,
            settings_path=str(settings_path),
        )

    assert settings.swarm_allow_external_llm_for_replies is False
    assert settings.swarm_allow_external_llm_for_scheduled is False
    assert settings.swarm_addressed_reply_rate_limit_count == 2
    assert settings.swarm_addressed_reply_rate_limit_window_seconds == 45
    assert settings.swarm_addressed_reply_max_pending_per_bot == 4
    assert settings.swarm_max_output_chars == 280
    assert settings.swarm_max_mentions_per_message == 1
    assert settings.swarm_history_retention_days == 7


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
        "OPENROUTER_API_KEY": "test_key",
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
        "OPENROUTER_API_KEY": "test_key",
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
        "OPENROUTER_API_KEY": "test_key",
        "PROXY": "http://user:pass@127.0.0.1:8080",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        settings = Settings(_env_file=None)
        watcher = SettingsReloadWatcher(settings)
        assert watcher.poll() is None
        settings_path.write_text(
            """
            [telegram]
            api_id = 87654321
            api_hash = "updated_api_hash"

            [openrouter]
            models = ["test/new-primary", "test/new-fallback"]

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
    assert reloaded.openrouter_api_key.get_secret_value() == "test_key"
    assert reloaded.api_id == 87654321
    assert reloaded.api_hash == "updated_api_hash"
    assert reloaded.openrouter_models == ["test/new-primary", "test/new-fallback"]
    assert reloaded.proxy is not None
    assert reloaded.proxy.get_secret_value() == "http://user:pass@127.0.0.1:8080"
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
        "OPENROUTER_API_KEY": "test_key",
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
                "OPENROUTER_API_KEY=test_key",
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
                "OPENROUTER_API_KEY=test_key",
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
        "OPENROUTER_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SESSION_STRING_MIKE": "mike-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        settings = Settings(_env_file=None)

    assert settings.mode == "swarm"
    assert settings.db_path == "data/history.db"
    assert settings.prompts_dir == "ai/prompts"
    assert settings.topics_path == "ai/prompts/topics.md"
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
        [swarm.schedule]
        active_windows_utc = {window_value}

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    env = {
        "OPENROUTER_API_KEY": "test_key",
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
        [swarm.schedule]
        responder_delay_minutes = {value}

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    env = {
        "OPENROUTER_API_KEY": "test_key",
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
        "OPENROUTER_API_KEY": "test_key",
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
        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    env = {
        "OPENROUTER_API_KEY": "test_key",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(Exception, match="SESSION_STRING_ANNA"):
            Settings(_env_file=None)


@pytest.mark.parametrize(
    ("toml_fragment", "key_name"),
    [
        ("[app]\nmode = \"swarm\"", "app"),
        ("[storage]\ndb_path = \":memory:\"", "storage"),
        ("[prompts]\nbase_dir = \"custom/prompts\"", "prompts"),
        ("[paths]\nreply_" + "rules_path = \"custom/rules.md\"", "paths"),
        (
            '[telegram]\napi_id = 12345678\napi_hash = "test_api_hash_abc"\nwhite'
            + "list_user_ids = [111, 222]",
            "white" + "list_user_ids",
        ),
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
        {toml_fragment}

        [[groups]]
        id = "danang"
        city = "Da Nang"
        group_chat_id = -100111

        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "anna.md"
        """,
    )

    env = {
        "OPENROUTER_API_KEY": "test_key",
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
        [[swarm.bots]]
        id = "anna"
        session_env = "SESSION_STRING_ANNA"
        persona_file = "{persona_file}"
        """,
    )

    env = {
        "OPENROUTER_API_KEY": "test_key",
        "SESSION_STRING_ANNA": "anna-session",
        "SETTINGS_PATH": str(settings_path),
    }

    with patch.dict("os.environ", env, clear=True):
        with pytest.raises(Exception, match="persona_file"):
            Settings(_env_file=None)


def _env_file_keys(path: Path) -> set[str]:
    """Возвращает только имена переменных из env-файла без чтения значений."""
    keys: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _value = line.split("=", maxsplit=1)
        keys.add(key.strip())
    return keys


def _require_local_prod_files() -> tuple[Path, Path]:
    """Возвращает локальные prod-файлы или пропускает тест в чистом checkout."""
    settings_path = Path("config/settings.prod.toml")
    env_path = Path(".env.prod")
    if not settings_path.exists() or not env_path.exists():
        pytest.skip("Локальные prod-файлы отсутствуют в этом checkout")
    return settings_path, env_path


def test_prod_settings_toml_is_valid_and_matches_env_sessions():
    """Проверяет prod TOML и соответствие session_env ключам .env.prod без вывода секретов."""
    settings_path, env_path = _require_local_prod_files()
    settings_data = tomllib.loads(settings_path.read_text(encoding="utf-8"))
    prod_env_keys = _env_file_keys(env_path)
    configured_session_keys = [
        bot["session_env"]
        for bot in settings_data["swarm"]["bots"]
    ]
    prod_session_keys = {
        key
        for key in prod_env_keys
        if key.startswith("SESSION_STRING_")
    }
    telegram = settings_data.get("telegram", {})

    assert configured_session_keys
    assert len(configured_session_keys) == len(set(configured_session_keys))
    assert set(configured_session_keys) == prod_session_keys
    assert isinstance(telegram.get("api_id"), int) and telegram["api_id"] > 0
    assert isinstance(telegram.get("api_hash"), str) and telegram["api_hash"].strip()
    assert "API_ID" not in prod_env_keys
    assert "API_HASH" not in prod_env_keys


def test_prod_settings_load_with_declared_session_keys():
    """Проверяет, что production TOML проходит строгую Settings-валидацию."""
    settings_path, _env_path = _require_local_prod_files()
    settings_data = tomllib.loads(settings_path.read_text(encoding="utf-8"))
    if "openrouter" not in settings_data:
        pytest.skip("Локальный production config ещё не мигрирован оператором на OpenRouter")
    env = {
        bot["session_env"]: "test-session"
        for bot in settings_data["swarm"]["bots"]
    }

    with patch.dict("os.environ", env, clear=False):
        settings = Settings(
            **BASE_SECRETS,
            settings_path=str(settings_path),
        )

    assert settings.swarm_bot_ids == [bot["id"] for bot in settings_data["swarm"]["bots"]]
    assert [bot.persona_file for bot in settings.swarm_bots] == [
        bot["persona_file"]
        for bot in settings_data["swarm"]["bots"]
    ]


def test_prod_settings_persona_files_exist():
    """Проверяет, что каждый production bot ссылается на существующий persona-файл."""
    settings_path, _env_path = _require_local_prod_files()
    settings_data = tomllib.loads(settings_path.read_text(encoding="utf-8"))
    persona_dir = Path("ai/prompts/bots")

    persona_files = [
        bot["persona_file"]
        for bot in settings_data["swarm"]["bots"]
    ]

    assert persona_files
    for persona_file in persona_files:
        assert (persona_dir / persona_file).exists(), f"Нет persona-файла: {persona_file}"
