## Context

`quarantined_swarm_bots` stores both durable group/account restrictions and a transient `__startup__` availability snapshot. Startup must preserve durable restrictions, but the configured profile list is the source of truth for which accounts can be launched in the current runtime.

## Goals / Non-Goals

**Goals:**

- Pass the current profile IDs into the durable quarantine query.
- Filter by exact textual IDs, including short and long numeric strings.
- Leave legacy rows in SQLite for auditability.

**Non-Goals:**

- Clearing quarantine rows automatically.
- Changing the meaning of global quarantine or startup availability.

## Decisions

- Add an optional `bot_ids` set to `get_quarantined_bot_ids`; build a parameterized `IN` clause and sort values for deterministic parameters.
- Keep `None` as the compatibility path that queries all durable rows; startup always supplies configured IDs.
- Treat IDs as strings rather than integers to support arbitrary Telegram/userbot identifiers without overflow or formatting changes.

## Risks / Trade-offs

- [Risk] A permanently restricted configured account remains excluded. → This is the intended safety behavior; removal requires an explicit quarantine-management action.
- [Risk] Legacy rows remain in the database. → They are retained for auditability but no longer affect unrelated runtimes.
