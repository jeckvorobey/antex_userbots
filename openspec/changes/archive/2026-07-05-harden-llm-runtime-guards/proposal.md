## Why

The current swarm runtime accepts any addressed human reply from an enabled group, sends raw chat context to an external LLM, and publishes model output back to Telegram without dedicated runtime safety guards. The code needs practical security controls that reduce abuse, data exposure, and unsafe output while preserving the existing swarm behavior model.

## What Changes

- Add configurable runtime guards for addressed human replies before any external Gemini call is made.
- Add configurable toggles that can disable external LLM usage for human replies and scheduled exchanges.
- Add output safety checks and safe fallback behavior before publishing model output to Telegram.
- Add retention cleanup for persisted message and exchange history so the runtime does not keep unbounded plaintext chat data forever.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `addressed-reply-routing`: Add abuse throttling, LLM enable/disable gates, and safe fallback behavior for addressed human replies.
- `runtime-configuration`: Add supported runtime settings for LLM safety guards and retention cleanup.
- `prompt-and-gemini`: Add request redaction and output safety validation around Gemini usage.
- `message-persistence`: Add retention cleanup behavior for persisted message and exchange history.

## Impact

- `core/config.py`: new supported security-oriented runtime settings.
- `userbot/reply_router.py`: rate limiting, LLM reply gating, and safe fallback flow.
- `userbot/orchestrator.py`: scheduled LLM gating and output safety handling.
- `ai/gemini.py`: input redaction and output validation helpers near the Gemini boundary.
- `ai/history.py` and `userbot/exchange_store.py`: retention cleanup helpers.
- Tests: config, router, orchestrator, Gemini, history, and exchange-store coverage for the new guards.
