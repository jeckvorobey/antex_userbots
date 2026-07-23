## Context

`SwarmManager` starts enabled userbots sequentially and executes the startup membership hook after each client connects. Both single-group and multi-group hooks currently select a random delay from one to three minutes before membership handling.

## Goals / Non-Goals

**Goals:**

- Keep a staggered startup delay while reducing each membership-check wait to 30–60 seconds inclusive.
- Keep randomness deterministic in tests and preserve existing membership behaviour and logging.

**Non-Goals:**

- Do not parallelize userbot startup or alter client-start ordering.
- Do not change reconnect backoff, scheduled-exchange delays, addressed-reply delay, or the public TOML configuration surface.

## Decisions

- Define the 30–60 second range as a module-level startup-membership constant in `run.py`; it is deployment behaviour, not operator-configurable runtime policy.
- Use a dedicated startup-delay selector in `run.py` rather than broadening the minute-based scheduler helper. This prevents accidental changes to scheduled exchange timing.
- Apply the same selector to both membership startup hooks so legacy single-group use and normal multi-group startup cannot drift.

## Risks / Trade-offs

- [Sequential startup still accumulates delay across bots] -> The task shortens each per-bot interval only; concurrent startup remains a separate Telegram-load decision.
- [Shorter staggering creates a modestly denser join burst] -> Keep the random 30–60 second offset and do not change join calls or reconnect policy.
