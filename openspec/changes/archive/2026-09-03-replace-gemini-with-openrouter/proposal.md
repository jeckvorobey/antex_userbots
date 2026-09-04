## Why

Gemini generation is blocked by provider billing and couples the runtime, configuration, prompts, and error handling to one vendor. The project needs a provider-neutral generation boundary backed by OpenRouter with ordered model fallback and strict zero-data-retention routing.

## What Changes

- **BREAKING** Replace `GEMINI_API_KEY`, `PROXY_URL`, and `[gemini]` with `OPENROUTER_API_KEY`, optional `PROXY`, and `[openrouter]`; legacy names are not accepted.
- Require an ordered `[openrouter].models` list with at least two unique non-empty model slugs and an optional temperature.
- Replace the Gemini SDK with the official async OpenRouter SDK and send Chat Completions through ZDR providers with provider and model fallback enabled.
- Split provider-neutral generation contracts, safety, prompt loading, and the OpenRouter adapter into focused modules.
- Rename runtime dependencies from `gemini_client` to `ai_client` while preserving the generation methods used by Telegram flows.
- Preserve safe logging, redaction, scheduled exchanges, addressed replies, config reload, and managed client shutdown.
- Rename the main `prompt-and-gemini` capability to provider-neutral `prompt-and-generation` and update dependent specifications and project documentation.
- Leave the active `humanize-production-personas` change unchanged; its Gemini Search design requires a later adaptation.

## Capabilities

### New Capabilities

- `prompt-and-generation`: Provider-neutral prompt loading, input/output safety, OpenRouter request behavior, retries, fallback, errors, and lifecycle.

### Modified Capabilities

- `prompt-and-gemini`: Remove the superseded Gemini-specific capability after its behavior is represented by `prompt-and-generation`.
- `runtime-configuration`: Replace Gemini and legacy proxy configuration with the strict OpenRouter and shared proxy contract.
- `addressed-reply-routing`: Route generation through the provider-neutral client and preserve safe fallback behavior.
- `scheduled-exchanges`: Route scheduled questions and replies through the provider-neutral client while preserving anti-repeat and persistence behavior.
- `swarm-runtime`: Build, share, reload, and close the OpenRouter-backed generation client and apply the shared proxy to Telegram and AI traffic.
- `message-persistence`: Keep persisted LLM drafts reusable without naming the removed provider.

## Impact

The change affects `core/config.py`, `run.py`, the AI package, Telegram routing/orchestration wiring, tests, dependency locks, examples, README, AGENTS.md, OpenSpec project context, and the listed main capabilities. It removes `google-genai`, adds `openrouter` and explicit async HTTPX proxy support, and requires operators to provide new credentials and model slugs before startup.
