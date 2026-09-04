## Why

The new OpenRouter path already enforces privacy-oriented routing, but it does not bound generated token cost, permits arbitrary model-authored links, and keeps provider credentials as ordinary strings. The current lock file also contains a known-vulnerable `cryptography` release.

## What Changes

- Cap OpenRouter completions at 256 tokens before provider generation.
- Reject generated output containing URLs other than the explicitly approved Mini App URL.
- Redact credential-bearing URLs before external generation.
- Keep the OpenRouter key and shared proxy in masked secret wrappers until client construction.
- Upgrade `cryptography` to a release containing the upstream PKCS#7 oracle fix.
- Extend regression tests and security documentation for the hardened contracts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `prompt-and-generation`: Bound provider completions, strengthen input redaction, and enforce an output URL allowlist.
- `runtime-configuration`: Represent environment-backed provider credentials as masked secret values until client construction.

## Impact

Affected areas include `ai/generation.py`, `ai/openrouter.py`, runtime wiring in `run.py`, Pydantic settings in `core/config.py`, the OpenRouter/config/runtime test suites, `pyproject.toml`, `uv.lock`, and the corresponding project documentation. No database schema or Telegram routing contract changes.
