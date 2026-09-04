"""Тесты для модуля настроек приложения."""

import logging
import os
from unittest.mock import patch

import pytest


# Базовый набор обязательных переменных окружения для тестов
BASE_ENV = {
    "OPENROUTER_API_KEY": "test_openrouter_key_xyz",
}


@pytest.fixture(autouse=True)
def isolate_cwd(tmp_path, monkeypatch):
    """Изолирует cwd, чтобы тесты не зависели от локального config/settings.toml."""
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "settings.toml").write_text(
        '[telegram]\napi_id = 12345678\napi_hash = "test_api_hash_abc"\n\n'
        '[openrouter]\nmodels = ["test/primary", "test/fallback"]\n',
        encoding="utf-8",
    )


def test_swarm_orchestrator_uses_60_second_default_tick():
    """Проверяет default cadence при отсутствии TOML override."""
    from core.config import SwarmOrchestratorConfig

    assert SwarmOrchestratorConfig().tick_seconds == 60


def test_settings_loads_telegram_credentials_from_toml():
    """Проверяет загрузку Telegram credentials из TOML."""
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from core.config import Settings

        s = Settings(_env_file=None)
        assert s.api_id == 12345678
        assert s.api_hash == "test_api_hash_abc"
        assert s.openrouter_api_key.get_secret_value() == "test_openrouter_key_xyz"


def test_settings_ignores_legacy_session_string():
    """Проверяет, что legacy session env key не входит в runtime-контракт."""
    legacy_key = "SESSION" + "_STRING"
    env = {**BASE_ENV, legacy_key: "test-session-string"}
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        s = Settings(_env_file=None)

    assert not hasattr(s, "session_string")


def test_settings_missing_openrouter_key_raises():
    """Проверяет обязательность OpenRouter key в окружении."""
    with patch.dict(os.environ, {}, clear=True):
        from core.config import Settings

        with pytest.raises(Exception):
            Settings(_env_file=None)


def test_settings_missing_session_string_is_allowed_for_swarm_setup():
    """Проверяет, что legacy session env key не требуется для swarm setup."""
    env_without_session_string = {
        "OPENROUTER_API_KEY": "test_key",
    }
    with patch.dict(os.environ, env_without_session_string, clear=True):
        from core.config import Settings

        settings = Settings(_env_file=None)

    assert not hasattr(settings, "session_string")


def test_settings_ignores_empty_legacy_session_string():
    """Проверяет, что пустой legacy session env key игнорируется."""
    legacy_key = "SESSION" + "_STRING"
    env = {
        "OPENROUTER_API_KEY": "test_key",
        legacy_key: "   ",
    }
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        settings = Settings(_env_file=None)

    assert not hasattr(settings, "session_string")


def test_load_settings_or_exit_logs_validation_error(monkeypatch, caplog, tmp_path):
    """Проверяет, что ошибка конфигурации логируется перед остановкой."""
    with patch.dict(os.environ, {}, clear=True):
        from core.config import get_settings, load_settings_or_exit

        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()
        with caplog.at_level(logging.CRITICAL):
            with pytest.raises(SystemExit, match="1"):
                load_settings_or_exit()

        messages = [record.getMessage() for record in caplog.records]
        assert any("Ошибка конфигурации" in message for message in messages)


def test_settings_has_db_path():
    """Проверяет наличие поля пути к базе данных."""
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from core.config import Settings

        s = Settings(_env_file=None)
        assert s.db_path is not None
        assert len(s.db_path) > 0


def test_get_settings_returns_settings_instance(monkeypatch, tmp_path):
    """Проверяет, что публичная фабрика возвращает объект Settings."""
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from core.config import Settings, get_settings

        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()
        settings = get_settings()

        assert isinstance(settings, Settings)
        assert settings.api_id == 12345678


def test_settings_reads_proxy():
    """Проверяет загрузку общего proxy из переменных окружения."""
    env = {**BASE_ENV, "PROXY": "http://user:pass@127.0.0.1:8080"}
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        s = Settings(_env_file=None)

        assert s.proxy is not None
        assert s.proxy.get_secret_value() == "http://user:pass@127.0.0.1:8080"


@pytest.mark.parametrize("scheme", ["http", "socks5"])
def test_settings_accepts_proxy_schemes_supported_by_both_clients(scheme):
    """Общий proxy принимает только транспортно совместимые рабочие схемы."""
    env = {**BASE_ENV, "PROXY": f"{scheme}://127.0.0.1:8080"}
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        settings = Settings(_env_file=None)

    assert settings.proxy is not None
    assert settings.proxy.get_secret_value() == f"{scheme}://127.0.0.1:8080"


@pytest.mark.parametrize("scheme", ["https", "socks4", "socks5h"])
def test_settings_rejects_proxy_scheme_unsupported_by_either_client(scheme):
    """Общая схема отклоняется, если хотя бы один transport её не поддерживает."""
    env = {**BASE_ENV, "PROXY": f"{scheme}://127.0.0.1:8080"}
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        with pytest.raises(ValueError, match="proxy scheme"):
            Settings(_env_file=None)


def test_settings_masks_openrouter_key_and_proxy():
    """Проверяет маскирование provider key и proxy credentials в диагностике."""
    env = {**BASE_ENV, "PROXY": "http://user:pass@127.0.0.1:8080"}
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        settings = Settings(_env_file=None)

    assert "test_openrouter_key_xyz" not in str(settings.openrouter_api_key)
    assert "test_openrouter_key_xyz" not in repr(settings.openrouter_api_key)
    assert "user:pass" not in str(settings.proxy)
    assert "user:pass" not in repr(settings.proxy)


def test_rejected_proxy_validation_hides_credentials():
    """Невалидная proxy-схема не раскрывает username/password в ValidationError."""
    env = {**BASE_ENV, "PROXY": "https://alice:pass123@example.com:443"}
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        with pytest.raises(ValueError) as exc_info:
            Settings(_env_file=None)

    error_text = str(exc_info.value)
    assert "alice" not in error_text
    assert "pass123" not in error_text


def test_settings_reads_group_target_from_env():
    """Проверяет загрузку целевой Telegram-группы из переменных окружения."""
    env = {
        **BASE_ENV,
        "GROUP_CHAT_ID": "-1001234567890",
        "GROUP_TARGET": "https://t.me/example_group",
    }
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        s = Settings(_env_file=None)

    assert s.group_chat_id == -1001234567890
    assert s.group_target == "https://t.me/example_group"


def test_settings_normalizes_empty_group_target_env():
    """Проверяет, что пустая строковая Telegram-цель отключается."""
    env = {**BASE_ENV, "GROUP_CHAT_ID": "0", "GROUP_TARGET": "   "}
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        s = Settings(_env_file=None)

    assert s.group_chat_id is None
    assert s.group_target is None


def test_settings_proxy_defaults_to_none():
    """Проверяет, что proxy по умолчанию отключён."""
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from core.config import Settings

        s = Settings(_env_file=None)

        assert s.proxy is None


def test_settings_log_level_defaults_to_info():
    """Проверяет, что уровень логирования по умолчанию равен INFO."""
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from core.config import Settings

        s = Settings(_env_file=None)

        assert s.log_level == "INFO"


def test_settings_log_file_defaults_to_logs_folder():
    """Проверяет, что путь лог-файла по умолчанию лежит в logs."""
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from core.config import Settings

        s = Settings(_env_file=None)

        assert s.log_file == "logs/swarm.log"


def test_settings_reads_openrouter_models_and_optional_temperature():
    """Проверяет порядок моделей и необязательную температуру OpenRouter."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        settings_path = Path(tmpdir) / "settings.toml"
        settings_path.write_text(
            """
            [telegram]
            api_id = 12345678
            api_hash = "test_api_hash_abc"

            [openrouter]
            models = [" vendor/primary ", "vendor/fallback"]
            temperature = 0.7
            """,
            encoding="utf-8",
        )
        env = {**BASE_ENV, "SETTINGS_PATH": str(settings_path)}

        with patch.dict(os.environ, env, clear=True):
            from core.config import Settings

            s = Settings(_env_file=None)

    assert s.openrouter_models == ["vendor/primary", "vendor/fallback"]
    assert s.openrouter_temperature == 0.7
    assert s.openrouter_request_timeout_seconds == 45.0
    assert s.openrouter_retry_initial_interval_ms == 500
    assert s.openrouter_retry_max_interval_ms == 5000
    assert s.openrouter_retry_max_elapsed_time_ms == 15000
    assert s.openrouter_retry_jitter_ms == 300


def test_settings_legacy_gemini_key_does_not_replace_required_openrouter_key():
    """Проверяет, что legacy Gemini key не заменяет обязательный OpenRouter key."""
    env = {
        "GEMINI_API_KEY": "legacy-key",
        "PROXY_URL": "http://legacy:secret@127.0.0.1:8080",
    }
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        with pytest.raises(Exception):
            Settings(_env_file=None)


def test_settings_ignores_legacy_gemini_and_proxy_url_when_new_key_exists():
    """Проверяет отсутствие legacy aliases при валидном новом контракте."""
    env = {
        **BASE_ENV,
        "GEMINI_API_KEY": "legacy-key",
        "PROXY_URL": "http://legacy:secret@127.0.0.1:8080",
    }
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        settings = Settings(_env_file=None)

    assert settings.proxy is None
    assert not hasattr(settings, "gemini_api_key")


@pytest.mark.parametrize("key", [None, "", "   "])
def test_settings_requires_non_empty_openrouter_key(key):
    """Проверяет обязательность непустого OpenRouter API key."""
    env = {}
    if key is not None:
        env["OPENROUTER_API_KEY"] = key
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        with pytest.raises(Exception):
            Settings(_env_file=None)


def test_settings_ignores_legacy_telegram_environment_variables():
    """Проверяет, что API_ID/API_HASH из env не заменяют значения TOML."""
    env = {
        **BASE_ENV,
        "API_ID": "87654321",
        "API_HASH": "legacy_env_hash",
    }
    with patch.dict(os.environ, env, clear=True):
        from core.config import Settings

        settings = Settings(_env_file=None)

    assert settings.api_id == 12345678
    assert settings.api_hash == "test_api_hash_abc"


def test_settings_exposes_swarm_security_defaults():
    """Проверяет кодовые defaults security-настроек swarm."""
    with patch.dict(os.environ, BASE_ENV, clear=True):
        from core.config import Settings

        settings = Settings(_env_file=None)

    assert settings.swarm_allow_external_llm_for_replies is True
    assert settings.swarm_allow_external_llm_for_scheduled is True
    assert settings.swarm_addressed_reply_rate_limit_count == 3
    assert settings.swarm_addressed_reply_rate_limit_window_seconds == 60
    assert settings.swarm_addressed_reply_max_pending_per_bot == 3
    assert settings.swarm_max_output_chars == 400
    assert settings.swarm_max_mentions_per_message == 2
    assert settings.swarm_history_retention_days == 30
