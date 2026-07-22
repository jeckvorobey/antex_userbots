## Why

`ExchangeStore` recent/due queries are scheduler hot paths and currently use SQLite timestamp functions and `COALESCE(...)` expressions in filters and ordering. As `scheduled_exchanges` grows, those expressions can reduce index usefulness and increase scan/sort work.

## What Changes

- Add a persisted `last_activity_at` timestamp to `scheduled_exchanges`.
- Backfill `last_activity_at` from existing lifecycle timestamps during idempotent initialization.
- Update exchange lifecycle writes so `last_activity_at` tracks planned, started, and completed state transitions.
- Rewrite due/recent/latest exchange queries to compare sortable UTC timestamp strings directly and order by indexed `last_activity_at`.
- Add group/chat indexes for `last_activity_at` based recent lookups.
- Cache normalized topic keys in `TopicSelector` so scheduler topic anti-repeat does not re-run regex normalization for every topic on every decision.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `message-persistence`: Add persisted exchange activity sort key and index-backed recent/due lookup behavior.
- `prompt-and-gemini`: Cache loaded topic intent keys while preserving topic loading and anti-repeat semantics.

## Impact

- `userbot/exchange_store.py`: SQLite migration, lifecycle writes, query predicates/order clauses, indexes.
- `userbot/scheduler.py`: cached topic key generation.
- `userbot/orchestrator.py`: use cached topic keys when available with fallback for test doubles.
- Tests: exchange-store migration/lifecycle/recent-order coverage and scheduler topic-key coverage.
