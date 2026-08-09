## Why

Persisted quarantine currently prevents a previously unavailable account from
reaching the Telegram startup check after a restart. Its state can therefore
outlive the account restriction that caused it and keep a configured bot out of
the working swarm.

## What Changes

- Rebuild the persisted availability snapshot for every configured enabled bot
  during application startup instead of trusting a previous quarantine record.
- Record whether each checked bot is globally available, is not frozen, and can
  write to every enabled group.
- Admit only bots that pass all startup checks to the active swarm pool.
- Remove stale availability data for bots removed from `settings.toml` as part
  of the snapshot reset.

## Capabilities

### New Capabilities

- `startup-swarm-availability-refresh`: Builds a fresh persisted availability
  snapshot and selects the startup swarm pool from it.

### Modified Capabilities

- `swarm-runtime`: Startup eligibility and active-pool behavior now depends on
  the fresh availability checks.

## Impact

- Affects `run.py`, `userbot/swarm_manager.py`, `userbot/exchange_store.py`,
  SQLite schema/migration handling, startup tests, runtime documentation, and
  OpenSpec runtime specifications.
- Does not change public HTTP APIs or add external dependencies.
