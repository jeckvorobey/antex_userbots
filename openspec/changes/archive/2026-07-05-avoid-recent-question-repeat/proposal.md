## Why

Scheduled initiator questions can still repeat a bot's own recent phrasing when the random pick lands on a topic that was already asked in the last few exchanges. We need the bot to avoid that visible repetition by consulting persisted history and switching to a different question before the message is sent.

## What Changes

- Keep the existing scheduled-exchange anti-repeat rule that retries when Gemini returns a question whose normalized signature already appeared recently.
- Add a second anti-repeat check for the specific initiator bot: compare the randomly generated question against that bot's last 5 persisted questions in the same group.
- If the random question matches one of those 5 recent initiator questions, reject it and ask Gemini for another random question instead of sending the repeat.
- Preserve the existing normalization rules so punctuation and spacing differences do not hide repeats.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `scheduled-exchanges`: Strengthen initiator question anti-repeat behavior with an additional per-bot recent-history check before delivery.

## Impact

- `userbot/orchestrator.py`: update scheduled initiator question selection to consult recent history before accepting the chosen question.
- `tests/test_orchestrator.py`: add coverage for the last-5 question repeat case and the fallback to a different question.
- `openspec/specs/scheduled-exchanges/spec.md`: refine the anti-repeat requirement to describe the recent-history check.
- No breaking API or config changes are expected.
