## Context

`TopicSelector` currently loads every non-comment line from `topics.md` as a candidate topic. `SwarmOrchestrator` passes the selected topic into Gemini via `GeminiClient.start_topic`, while `PromptComposer` adds group city/id context to `start_topic.md`. This is enough if topics are universal intents, but wrong if topics are already city-specific questions.

## Goals / Non-Goals

**Goals:**
- Keep one shared topic file for all groups.
- Make the initiator adapt each topic intent to the group city at generation time.
- Track real prompts and personas in git for the single instance.
- Remove prompt templates and unused prompt rules that no runtime code reads.

**Non-Goals:**
- No separate `topics_path` per group.
- No new prompt templating engine.
- No change to Telegram routing, storage, bot sessions, or group reload behavior.

## Decisions

- Store topic intents as short generic lines without embedded city names. This keeps `TopicSelector` simple and keeps anti-repeat based on semantic topics.
- Put city adaptation rules in `start_topic.md` and rely on existing orchestrator group context. This avoids adding a new Gemini API parameter.
- Keep `reply.md` as the place for exchange-related answer policy. `reply_rules.md` is removed because it is not loaded by runtime.
- Track real `ai/prompts/**/*.md` in git. Secrets remain in `.env`; prompts must not contain session strings or API keys.

## Risks / Trade-offs

- Generic topics need better prompt instructions to avoid bland questions. Mitigation: make `start_topic.md` explicit that the generated question must be concrete for the city.
- Tracking real personas makes content review part of git review. Mitigation: tests guard against `.example.md` contract drift and secret-like content remains covered by repository security checks.
