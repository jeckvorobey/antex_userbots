## 1. Tests

- [x] 1.1 Add or update production persona tests that require `## Манера общения` to avoid habitual marker-openers and describe natural starts.
- [x] 1.2 Add or update start-topic prompt tests that require the shared opening variants.

## 2. Prompt And Persona Content

- [x] 2.1 Update `ai/prompts/bots/*.md` communication style, chat behavior, and habits so each persona avoids recognizable opener habits without flattening character voice.
- [x] 2.2 Update `ai/prompts/start_topic.md` with the shared ordinary-human opening rule.

## 3. Validation And Specs

- [x] 3.1 Run the focused prompt/persona tests.
- [x] 3.2 Run `uv run pytest` if focused tests pass.
- [x] 3.3 Run `openspec validate --strict --all`.
- [x] 3.4 After implementation, sync specs with `openspec-sync-specs` and archive the completed change with `openspec-archive-change`.
