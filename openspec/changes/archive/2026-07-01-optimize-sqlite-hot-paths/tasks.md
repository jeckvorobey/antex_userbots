## 1. Tests

- [x] 1.1 Add tests that `MessageHistory.init_db` creates expected indexes idempotently.
- [x] 1.2 Add tests that `ExchangeStore.init_db` creates expected indexes idempotently.
- [x] 1.3 Extend recent bot id tests to prove SQL-limited retrieval preserves order and limit.

## 2. Implementation

- [x] 2.1 Add idempotent index creation helpers for `messages`.
- [x] 2.2 Add idempotent index creation helpers for `scheduled_exchanges`.
- [x] 2.3 Rewrite `get_recent_bot_ids` to deduplicate and limit in SQL.

## 3. Verification

- [x] 3.1 Run focused persistence tests.
- [x] 3.2 Run `uv run pytest`.
- [x] 3.3 Run `openspec validate --all --strict`, sync specs, and archive the change.
