## Why

The current runtime binds the whole swarm to one Telegram group, so city chats share schedule state, anti-repeat history, and runtime routing. The swarm must run one shared userbot pool across multiple city groups without restarting for simple group enable/disable changes.

## What Changes

- **BREAKING** Replace single `[target]` TOML config with `[[groups]]` entries containing `id`, `city`, `enabled`, `group_chat_id`, `group_target`, and optional schedule overrides.
- Keep secrets and bootstrap values in `.env`; remove `GROUP_CHAT_ID` and `GROUP_TARGET` from the example and treat them only as legacy overrides.
- Add non-mutating settings reload by TOML `mtime` so newly enabled groups are resolved for active bots and disabled groups stop routing/scheduling.
- Scope addressed replies, scheduled exchanges, message history, and anti-repeat queries by group.
- Persist `group_id` and real `group_chat_id` on scheduled exchange records and migrate existing SQLite databases idempotently.
- Add city/group runtime context to scheduled prompts without introducing separate topic files.

## Capabilities

### New Capabilities

### Modified Capabilities
- `runtime-configuration`: multi-group TOML schema, schedule inheritance, and reload watcher.
- `swarm-runtime`: membership/resolve flow for all enabled groups and reload updates.
- `scheduled-exchanges`: per-group orchestrator ticks and group-scoped scheduling.
- `message-persistence`: group-scoped scheduled exchange persistence and real group chat ids in history.
- `addressed-reply-routing`: reply handling only for enabled configured groups.
- `prompt-and-gemini`: scheduled prompts receive city/group context.

## Impact

Affected modules include `core/config.py`, `core/runtime_models.py`, `run.py`, `userbot/orchestrator.py`, `userbot/reply_router.py`, `userbot/exchange_store.py`, tests, `.env.example`, `config/settings.example.toml`, README, and OpenSpec specs. Existing deployments must migrate TOML from `[target]` to `[[groups]]`.
