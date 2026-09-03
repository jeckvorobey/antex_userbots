# Implementation tasks

- [x] 1. Add failing configuration tests for required TOML Telegram credentials, validation, ignored legacy env values, and reload behavior.
- [x] 2. Add `TelegramConfig`, remove Telegram credentials from `Secrets`, and load/reload them from TOML.
- [x] 3. Move Telegram placeholders from `.env.example` to `config/settings.example.toml` and update documentation/specs.
- [x] 4. Migrate local `.env`/`.env.prod` credentials into their matching ignored TOML files without exposing values.
- [x] 5. Run the full test suite and strict OpenSpec validation.
- [x] 6. Sync the delta into main specs and archive this change only.
