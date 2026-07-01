## 1. Specification And Tests

- [x] 1.1 Add OpenSpec delta specs for city-aware prompt/topic architecture.
- [x] 1.2 Update tests to expect real prompt files instead of `*.example.md`.
- [x] 1.3 Add tests that shared topics do not contain fixed city names and start-topic prompt requires city adaptation.

## 2. Prompt Architecture

- [x] 2.1 Replace prompt examples with real `system.md`, `reply.md`, `start_topic.md`, `wind_down_hint.md`, and tracked persona files.
- [x] 2.2 Rewrite `topics.md` as shared topic intents without city-specific ready questions.
- [x] 2.3 Remove unused `reply_rules.md`.
- [x] 2.4 Update `.gitignore` so real prompt files are tracked.

## 3. Documentation And Verification

- [x] 3.1 Update README, config comments, and main OpenSpec specs.
- [x] 3.2 Run `uv run pytest`.
- [x] 3.3 Run `openspec validate --all --strict`, sync specs, and archive the completed change.
