## Context

The current scheduler runs a `SwarmOrchestrator` per enabled group. Each orchestrator tick first completes due responders, then applies group active-window and human-activity gates, enforces one exchange per computed window key, chooses an ordinary topic from `TopicSelector`, and persists the exchange in SQLite.

Important service exchanges need stricter behavior than adding lines to `ai/prompts/topics.md`: they must be due on a per-group cadence, rotate through a fixed sequence, survive restarts, and use prompt instructions that mention `@tt_exchenge_bot` only in the responder answer.

## Goals / Non-Goals

**Goals:**

- Add a persisted per-group important-service exchange cadence.
- Rotate scenarios in this exact order: `exchange_rub`, `booking_airbnb`, `exchange_usdt`, `booking_booking`.
- Treat eligibility as calendar-day based: after an important exchange on day N for a group, the next important exchange is eligible no earlier than day N+3 for that same group.
- Reuse existing active-window, human-activity, one-window, bot cooldown, responder delay, and history persistence behavior.
- Add prompt context/rules that keep ordinary scheduled exchanges non-promotional and make important answers naturally mention `@tt_exchenge_bot`.

**Non-Goals:**

- No new HTTP API, FastAPI service, PostgreSQL, Redis, or external scheduler.
- No configurable admin UI for the scenario cycle.
- No hardcoded final message text in Python; scenario intents are allowed in code, but Gemini still generates the conversational wording through prompt files.
- No change to addressed human reply routing.

## Decisions

### Use a typed important-service exchange inside `scheduled_exchanges`

Add exchange metadata to the existing table rather than creating a second scheduler or second exchange table. Proposed fields:

- `exchange_kind`: `regular` or `important_service`
- `important_scenario`: one of `exchange_rub`, `booking_airbnb`, `exchange_usdt`, `booking_booking`

Rationale: existing lifecycle, due responder, group scoping, window key, message ids, and anti-repeat queries already model a two-message A -> B exchange. Extending the same table keeps the state machine simple and preserves restart behavior.

Alternative considered: separate `important_service_state` table. This would make due checks easier to query but would duplicate group/window lifecycle state and increase migration surface.

### Compute cadence from completed important exchanges per group

Eligibility should be derived from persisted completed/started important-service exchanges for the same group. If the latest important exchange date is day N in UTC, the next one is eligible on or after day N+3.

Rationale: the project currently uses UTC schedule windows, so UTC calendar days are the least surprising and avoid local timezone dependencies. Per-group lookup matches the user's requirement that cadence is independent for every group.

Alternative considered: strict `timedelta(days=2)`. That would allow a message late on July 5 and the next late on July 7, which conflicts with the example where July 5 allows the next important exchange only on July 8.

### Important exchanges replace the ordinary topic for an eligible window

During an eligible tick, the orchestrator should decide whether the current group's next exchange is important before choosing a normal topic. The existing one-exchange-per-window check remains the conflict guard.

Rationale: the important exchange should "вклиниваться" into the normal schedule, not create an extra message on top of a regular exchange.

Alternative considered: create a separate APScheduler job. That would compete with the existing group orchestrator and weaken the current one-window invariant.

### Keep scenario wording in prompt context, not final strings

The orchestrator should pass an important-service context containing:

- marker: `important_service_question` for initiator generation
- marker: `important_service_answer` for responder generation
- scenario key
- question intent
- answer intent
- required username `@tt_exchenge_bot`

Prompt files decide style constraints. Python must not store final generated answers.

Rationale: this preserves the existing prompt-file contract and lets Gemini vary wording while tests can still assert context and prompt rules.

### Preserve ordinary prompt behavior explicitly

`start_topic.md` and `reply.md` should state that promotional service guidance applies only when the exchange context carries the important-service marker. Ordinary money/exchange topics may remain neutral and must not automatically become ads.

Rationale: the current `reply.md` already permits a neutral contact mention only when useful. The new behavior must not leak into all ordinary replies.

## Risks / Trade-offs

- Repeated advertising can look unnatural → Mitigation: cap cadence per group, rotate scenarios, and require varied short conversational answers.
- Calendar-day cadence can be sensitive to UTC date boundaries → Mitigation: document and test UTC-day behavior because active windows are already UTC.
- Existing anti-repeat queries may treat important topics as recent ordinary topics → Mitigation: keep important scenario topic keys distinct and continue using question-signature anti-repeat.
- Migration must be safe for existing SQLite files → Mitigation: add nullable/defaulted columns idempotently and keep old rows as `regular` by default.

## Migration Plan

1. Add idempotent SQLite columns and indexes for exchange kind/scenario lookup.
2. Existing rows without `exchange_kind` behave as `regular`.
3. Implement and test store helpers before orchestrator behavior.
4. Update prompt files and tests so important-service markers are explicit.
5. Sync main specs and archive after tests pass.

Rollback is safe at code level because old rows remain compatible. If a deploy is rolled back after adding columns, older code ignores the extra SQLite columns.

## Open Questions

None. The username is fixed as `@tt_exchenge_bot`; cadence is per group; active windows reuse current settings; Airbnb and Booking scenarios rotate separately.
