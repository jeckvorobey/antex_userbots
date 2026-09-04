# Design: Telegram credentials in TOML

## Decision

`AppConfig` owns a required `TelegramConfig` section. `Settings` resolves the settings path from explicit input or `SETTINGS_PATH`, loads TOML, and exposes `api_id` and `api_hash` from `[telegram]`. Environment loading no longer declares or aliases `API_ID` and `API_HASH`.

The credentials remain operator-owned data: tracked examples contain placeholders, while real `config/settings.toml` and `config/settings.prod.toml` remain ignored by Git.

## Reload behavior

`SettingsReloadWatcher` reconstructs `Settings` with the same environment-backed OpenRouter key, proxy, and target overrides, but reads Telegram credentials again from the changed TOML file.

## Validation

The TOML model requires a positive integer `api_id` and a non-empty trimmed `api_hash`. Missing or invalid values fail during settings loading before Telegram clients are initialized. Legacy environment variables are ignored.
