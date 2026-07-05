## Why

Scheduled exchanges currently choose ordinary topic intents from the shared topic pool and only avoid recent repetitions. The service now needs predictable, per-group promotional question-answer exchanges about exchange and booking services that appear naturally inside the existing morning/evening schedule without becoming repetitive advertising.

## What Changes

- Add a distinct important-service exchange path that can replace an ordinary scheduled topic when it is due for a group.
- Track important-service cadence independently per group so a group that received an important exchange on day N is not eligible again until day N+3.
- Persist and rotate the important-service scenario cycle:
  - exchange RUB
  - Airbnb booking/payment
  - exchange USDT
  - Booking.com booking/payment
- Keep important exchanges inside the group's existing `active_windows_utc`, human-activity skip gate, one-exchange-per-window rule, bot cooldown, and responder delay flow.
- Add prompt context and prompt-file rules so important questions sound like ordinary chat questions, important answers naturally mention `@tt_exchenge_bot`, and ordinary exchanges do not turn into service advertising.
- Keep generated important answers varied rather than copying a fixed promotional sentence.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `scheduled-exchanges`: Add important-service exchange eligibility, per-group cadence, scenario rotation, and integration with existing active-window scheduling.
- `message-persistence`: Persist important-service exchange kind/scenario metadata and expose group-scoped lookup helpers for cadence and rotation.
- `prompt-and-gemini`: Add prompt behavior for important-service question and answer contexts while preserving ordinary scheduled topic behavior.

## Impact

- `userbot/orchestrator.py`: Select important-service scenarios when due, build specialized context, and keep ordinary scheduling rules intact.
- `userbot/exchange_store.py`: Add idempotent SQLite migration fields and group-scoped queries for latest important-service exchange state.
- `ai/prompts/start_topic.md` and `ai/prompts/reply.md`: Add non-conflicting instructions for important-service contexts.
- Tests: Add async unit coverage for cadence, scenario rotation, persistence migration/query behavior, and prompt contracts without calling Gemini, Telethon, or external SQLite files.
- Documentation and OpenSpec main specs require sync after implementation.
