## Context

Scheduled exchanges are evaluated for every enabled group on every scheduler tick. `ExchangeStore` already uses group-scoped indexes, but several queries wrap timestamp columns with `datetime(...)` and sort by `COALESCE(...)`, which can force SQLite to do extra work instead of using composite indexes efficiently.

Topic anti-repeat also normalizes every loaded topic on each decision even though the topic file is loaded once at runtime.

## Goals / Non-Goals

**Goals:**

- Preserve existing exchange lifecycle behavior and output ordering.
- Make recent/latest exchange queries use a persisted sortable timestamp key.
- Keep legacy SQLite migrations idempotent.
- Reduce repeated topic normalization in the scheduler path.

**Non-Goals:**

- No change to user-facing scheduling cadence, prompts, Telegram behavior, or config format.
- No new database engine or external cache.
- No broad query rewrite outside proven hot paths.

## Decisions

### Persist `last_activity_at`

Store a single lifecycle sort key on `scheduled_exchanges`. New rows receive `CURRENT_TIMESTAMP`, `mark_exchange_started` updates it to the same value as `started_at`, and `mark_exchange_completed` updates it to the same value as `completed_at`.

Rationale: this removes repeated `COALESCE(completed_at, started_at, created_at)` expressions from hot queries while preserving the same logical ordering.

### Compare SQLite UTC strings directly

The project serializes timestamps as `YYYY-MM-DD HH:MM:SS` UTC strings. That format is lexicographically sortable, so direct comparisons preserve order without wrapping columns in `datetime(...)`.

Rationale: direct comparison allows indexes on timestamp columns to be more useful.

### Cache topic keys in `TopicSelector`

Build `topic_keys` during `TopicSelector.load()` and expose `topic_key(topic)`. `SwarmOrchestrator` uses it when available and falls back to `normalize_signature` for simple test doubles.

Rationale: this is a safe constant-factor optimization that does not change topic text or selection semantics.

## Risks / Trade-offs

- Legacy rows without lifecycle timestamps can keep `last_activity_at = NULL` → mitigated by preserving existing behavior for rows without usable timestamps and backfilling all rows that have lifecycle data.
- Existing indexes remain alongside newer indexes → acceptable for compatibility; cleanup can happen later if measured as necessary.
- Topic key normalization is duplicated between scheduler and exchange store → acceptable to avoid a larger module reshuffle; tests assert matching behavior for important cases.
