## Why

SQLite tables `messages` and `scheduled_exchanges` grow continuously during bot operation. Current hot-path history and anti-repeat queries rely on scans/sorts without supporting indexes, and `get_recent_bot_ids` transfers all candidate events before applying the requested limit in Python.

## What Changes

- Add idempotent SQLite indexes for message history lookups by user, chat, bot, and session timestamp.
- Add idempotent SQLite indexes for scheduled exchange window, due responder, and recent anti-repeat queries.
- Optimize `ExchangeStore.get_recent_bot_ids` so unique recent bot selection is limited in SQL while preserving the current message-order semantics.
- Keep runtime behavior, public method signatures, migrations, and tests compatible.

## Capabilities

### New Capabilities

### Modified Capabilities
- `message-persistence`: SQLite persistence must create indexes for hot-path history/exchange queries and keep recent bot id retrieval bounded by the requested limit.

## Impact

Affected modules are `ai/history.py`, `userbot/exchange_store.py`, and focused persistence tests. No Telegram, Gemini, prompt, config, or scheduler public behavior changes are intended.
