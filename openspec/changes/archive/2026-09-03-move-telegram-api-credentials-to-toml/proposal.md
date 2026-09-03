# Change: Move Telegram API credentials to TOML

## Why

Telegram `api_id` and `api_hash` belong to the instance configuration and should be stored with the rest of the Telegram runtime settings. Keeping them in `.env` makes operator setup unnecessarily split across two files.

## What Changes

- Add a required `[telegram]` TOML section with `api_id` and `api_hash`.
- Stop reading `API_ID` and `API_HASH` from environment sources.
- Keep `OPENROUTER_API_KEY`, optional `PROXY`, and Telethon session strings in environment sources.
- Reload Telegram credentials from TOML when the settings file changes.
- Update examples, documentation, tests, and operator-owned local configuration files.

## Impact

- Affected capability: `runtime-configuration`.
- Affected code: `core/config.py`, configuration tests, examples, and README.
- Operator migration: move existing Telegram credentials from `.env*` to the matching `config/settings*.toml` files.
