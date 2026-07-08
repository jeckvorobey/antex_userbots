## Why

Bots are currently too easy to identify because some persona profiles describe repeated opening markers such as "кстати", "слушай", "слушайте", and "смотри" as normal habits. Real group participants usually start with neutral greetings like "привет", "всем привет", "здравствуйте", or ask directly without an introductory marker, so bot persona communication style should be edited to make openings less formulaic.

## What Changes

- Edit production bot persona `## Манера общения` sections so they no longer present overused attention-grabbing openers as frequent interjections, favorite phrases, or habitual starts.
- Clarify natural openings inside persona style: direct answer, direct question, immediate reaction, or simple greeting when contextually appropriate.
- Add the same opening principle to the shared start-topic prompt: `привет`, `всем привет`, `здравствуйте`, or a direct question without an introductory word.
- Add tests that validate persona communication style avoids the marker-openers and does not rely on a separate `## Ограничения` directive.
- No changes to Telegram routing, scheduling, database schema, configuration format, or external services.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `production-personas`: production persona profiles must describe natural communication starts in `## Манера общения` without encoding recognizable opener habits.
- `prompt-and-gemini`: scheduled start-topic generation must define the allowed ordinary-human opening variants.

## Impact

- Affected persona files: `ai/prompts/bots/*.md`.
- Affected tests: prompt/persona validation tests, likely in `tests/test_gemini.py`.
- Affected specs: `openspec/specs/production-personas/spec.md` and `openspec/specs/prompt-and-gemini/spec.md` through delta specs for this change.
- No dependency, API, runtime architecture, or persistence impact.
