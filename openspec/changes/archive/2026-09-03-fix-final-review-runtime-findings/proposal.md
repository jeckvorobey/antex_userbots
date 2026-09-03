## Why

Дополнительный Codex Review подтвердил четыре runtime-дефекта: reload может сохранить прежний scheduled LLM gate или восстановить удалённую группу, important-service fallback теряет обязательную ссылку, а ошибка SQLite может оставить Telegram-ограниченный аккаунт активным. Эти ветки требуют устранения до merge PR #18.

## What Changes

- Инвалидировать cached group orchestrator при изменении scheduled LLM gate.
- Не передавать производные group compatibility fields в Settings reload.
- Использовать безопасный scenario-aware fallback с разрешённой Mini App ссылкой для important-service ответа.
- Гарантированно отключать аккаунт при permanent Telegram restriction, даже если запись quarantine завершилась ошибкой, после чего сохранять исходную ошибку для диагностики.
- Добавить регрессионные тесты, обновить OpenSpec и документацию.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `runtime-configuration`: reload должен сохранять только исходные environment fallback values, не derived group state.
- `swarm-runtime`: cache signature должна учитывать scheduled LLM gate, а permanent restriction всегда отключает аккаунт независимо от persistence failure.
- `prompt-and-generation`: important-service safe fallback должен сохранять обязательную разрешённую ссылку.

## Impact

Изменения затрагивают `core/config.py`, `run.py`, `userbot/orchestrator.py`, связанные тесты, README и три существующих OpenSpec capability. Схема TOML, БД и внешние зависимости не меняются.
