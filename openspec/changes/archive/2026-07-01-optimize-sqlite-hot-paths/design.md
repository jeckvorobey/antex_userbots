## Context

The application uses one SQLite file for both chat history and scheduled exchange state. Scheduled ticks call group-scoped exchange queries repeatedly, while addressed replies and scheduled responder generation load chat/bot history. Without indexes, these queries can degrade as tables grow.

## Goals / Non-Goals

**Goals:**
- Preserve every current query result and ordering contract.
- Make SQLite initialization idempotently create indexes.
- Reduce `get_recent_bot_ids` Python-side unbounded fetch.

**Non-Goals:**
- No orchestrator object caching in this change; that is lower impact and has stale-settings risk.
- No schema rewrite, denormalized event table, or cleanup/retention policy.
- No benchmark harness unless tests reveal ambiguous behavior.

## Decisions

- Use `CREATE INDEX IF NOT EXISTS` during existing `init_db` flows. This keeps migrations simple and safe for existing databases.
- Add separate indexes matching current query predicates instead of one broad catch-all index.
- Use a CTE plus `ROW_NUMBER() OVER (PARTITION BY bot_id ...)` in `get_recent_bot_ids` to keep the newest event per bot in SQL, then order those newest events and `LIMIT ?`.

## Risks / Trade-offs

- SQLite window functions require modern SQLite. Python 3.11+ bundled SQLite is expected to support them; tests will execute the query.
- Extra indexes make writes slightly more expensive. Scheduled/message writes are low volume compared with read frequency on ticks and replies.
