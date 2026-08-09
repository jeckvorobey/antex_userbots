## Context

`quarantined_swarm_bots` is durable state for permanent Telegram errors. The
current startup path reads it before starting clients, so a recovered account
does not execute the existing global messaging, frozen-account, membership,
or write-permission checks. The application uses asyncio and a shared SQLite
connection; it must not use threads for Telethon or SQLite work.

## Goals / Non-Goals

**Goals:**

- Rebuild a fresh, durable startup availability snapshot for all enabled
  configured bots.
- Require global Telegram messaging availability, no frozen-account error, and
  `can_write=True` for every enabled group before a bot becomes active.
- Run independent preflight checks with bounded asyncio concurrency.
- Make stale bot ids disappear from persisted state on every startup reset.

**Non-Goals:**

- Do not change `enabled = false` semantics.
- Do not publish messages to test availability.
- Do not alter runtime quarantine behavior after a permanent send error.

## Decisions

### Replace the old quarantine snapshot before startup

Startup deletes all rows in `quarantined_swarm_bots`, then records the result
for each checked enabled bot. This deliberately makes the database a snapshot
of the current startup rather than a permanent manual lock.

### Record explicit availability

The table gains `is_available INTEGER NOT NULL DEFAULT 0` and `checked_at`.
One global row per bot uses the stable `__startup__` group key. A failed group
permission produces an unavailable global row with a non-secret reason;
per-group diagnostic details remain in logs. This preserves the existing table
and migration path while giving the startup pool an unambiguous flag.

### Preflight before active-pool registration

Each enabled profile is started and checked before it is registered as active.
The existing non-publishing global messaging check detects frozen/deactivated/
revoked/banned accounts. Membership resolution then derives `can_write` for
every enabled group. Only a profile that passes all checks is registered.

### Bounded asynchronous concurrency

Use `asyncio` tasks guarded by a semaphore, with a small fixed concurrency
limit. This improves startup time without sharing clients across threads or
causing an unbounded Telegram connection burst.

## Risks / Trade-offs

- [Application stops during refresh] → rows may be incomplete, but the next
  startup clears and rebuilds the snapshot before using it.
- [Telegram rate limits] → bounded concurrency and existing startup delay are
  retained.
- [A group-specific restriction] → account is conservatively unavailable until
  a later startup confirms `can_write=True` for every enabled group.
- [Legacy callers expect only failures in quarantine] → runtime availability
  reads use the new explicit `is_available` flag; tests cover both outcomes.

## Migration Plan

1. Add the two SQLite columns idempotently.
2. On deployment restart, reset the old rows and build the new snapshot.
3. Rollback is safe: the old code ignores the added columns; the next old-code
   startup can still read `bot_id` rows.

## Open Questions

None.
