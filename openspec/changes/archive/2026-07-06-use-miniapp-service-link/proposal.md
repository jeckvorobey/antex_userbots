## Why

Important-service replies currently mention `@tt_exchenge_bot`, which renders as a plain Telegram username mention and does not provide the miniapp entry point the chat should promote. The responder should point users to the TT Exchange miniapp link instead.

## What Changes

- Replace the required important-service contact in generated responder context from `@tt_exchenge_bot` to `https://t.me/tt_exchenge_bot/antex`.
- Update reply prompt guidance so important-service answers naturally include the miniapp URL, not the username mention.
- Keep ordinary replies and start-topic questions non-promotional unless the `important_service_answer` marker is present.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `prompt-and-gemini`: Important-service responder messages must mention the TT Exchange miniapp URL instead of the plain bot username.

## Impact

- Affected files: `userbot/orchestrator.py`, `ai/prompts/reply.md`, prompt/orchestrator tests, README, and `openspec/specs/prompt-and-gemini/spec.md`.
- No dependency, database, scheduler, routing, or Telegram client API changes.
