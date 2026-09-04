## 1. Runtime config and persistence

- [x] 1.1 Add `swarm.security` runtime settings and defaults to `Settings`.
- [x] 1.2 Add retention cleanup helpers for message history and scheduled exchanges and call them during runtime bootstrap.

## 2. Gemini boundary guards

- [x] 2.1 Add request redaction helpers for obvious secret-like strings and Telegram invite links before Gemini requests.
- [x] 2.2 Add output safety validation and safe fallback helpers for model-generated text.

## 3. Reply and scheduled flow hardening

- [x] 3.1 Add addressed-reply rate limiting before Gemini calls.
- [x] 3.2 Add reply-path LLM gating and safe fallback responses.
- [x] 3.3 Add scheduled-exchange LLM gating and safe fallback handling for initiator and responder messages.

## 4. Verification

- [x] 4.1 Add or update tests for config, Gemini redaction/output safety, reply throttling, scheduled gating, and retention cleanup.
- [x] 4.2 Run the relevant pytest suites and strict OpenSpec validation.
