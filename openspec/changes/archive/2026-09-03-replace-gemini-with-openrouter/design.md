## Context

The runtime currently instantiates one `GeminiClient` that combines prompt loading, redaction, output validation, SDK calls, retries, and provider-specific response parsing. Configuration requires `GEMINI_API_KEY`, accepts `PROXY_URL`, and supplies Gemini model and retry fields from TOML. Reply routing and scheduled exchanges depend on the concrete client name even though they only need three generation methods.

The approved migration removes Gemini completely. OpenRouter receives the same redacted conversational context through Chat Completions and performs model fallback from an ordered list. The application remains async, has no HTTP server, and must never log credentials, prompts, history, raw provider errors, or private Telegram data.

The active `humanize-production-personas` change assumes Gemini Search. This migration neither applies nor rewrites that change; it will need a separate adaptation before it can be implemented.

## Goals / Non-Goals

**Goals:**

- Introduce provider-neutral contracts for text generation, errors, prompt loading, redaction, and output safety.
- Use the official `openrouter>=1.1.122,<2` async SDK and `chat.send_async` with ordered models.
- Require ZDR-compatible providers and deny data collection on every request.
- Apply one optional `PROXY` to Telethon and OpenRouter, with direct connections when absent.
- Preserve current reply and scheduled-exchange behavior, lifecycle, safety fallback, and configuration reload.
- Keep timeout and retry behavior bounded and testable without network calls.

**Non-Goals:**

- MCP, web search, Responses API, fine-tuning, agent loops, tools, streaming, or per-bot provider/model selection.
- Choosing production model slugs or creating Telegram accounts/session strings.
- Applying or modifying `humanize-production-personas`.
- Live OpenRouter or Telegram verification before the operator supplies secrets and test accounts.

## Decisions

### Provider-neutral module boundaries

`ai/generation.py` defines `TextGenerationClient`, `GenerationError`, `TemporaryGenerationError`, input redaction, and output validation. `ai/prompt_loader.py` owns prompt-file loading. `ai/openrouter.py` contains only OpenRouter request construction, response parsing, error mapping, retry setup, and lifecycle. This preserves the existing public methods while making Telegram consumers independent of a provider implementation.

Keeping the existing combined file or retaining Gemini as a second provider was rejected because the approved scope is a full replacement and the old names would keep configuration and runtime coupled to Gemini.

### Configuration contract

Secrets require `OPENROUTER_API_KEY`; optional `PROXY` is normalized to `None`. TOML requires `[openrouter].models` with at least two unique, trimmed, non-empty strings in operator-defined order. `temperature` is optional and has no implicit provider override. Unknown and legacy fields remain forbidden by strict Pydantic models.

The timeout is fixed at 45 seconds. Retry policy is code-managed because operators should not silently weaken bounded failure behavior: exponential backoff starts at 500 ms, caps each interval at 5000 ms, stops after 15000 ms elapsed, adds up to 300 ms jitter, and retries connection errors plus 408, 429, all 5xx statuses, 524, and 529. Explicit 524 and 529 entries document intent even though `5XX` also covers them.

### OpenRouter request and response

Each call passes two messages: a `system` message containing the already composed instruction and a `user` message containing redacted history/message or topic context. The call uses `models` rather than `model`, `stream=False`, and provider preferences `{zdr: true, data_collection: "deny", allow_fallbacks: true, require_parameters: true}`. Temperature is included only when configured.

The adapter extracts the first choice's message content and rejects missing, non-string, or whitespace-only output. SDK timeout and retry objects are configured centrally. Temporary transport/status failures map to `TemporaryGenerationError`; other SDK failures and malformed responses map to `GenerationError`. Logs contain only operation type, safe status/category, model count, and a credential-free proxy description.

### Proxy and lifecycle

When `PROXY` is present, runtime passes it to the existing Telethon proxy builder and supplies OpenRouter with a dedicated `httpx.AsyncClient(proxy=...)`. The adapter owns and closes both the SDK lifecycle and any injected HTTPX client exactly once. Without `PROXY`, the SDK creates its normal direct async transport and the adapter closes it through the SDK async context exit.

Runtime builds one shared `OpenRouterClient`, injects it as `ai_client`, reuses it across bot routers and per-group orchestrators, and closes it during shutdown. Settings reload updates runtime configuration through the existing replacement-settings flow; provider credentials remain sourced from the same environment context.

### Dependency migration

Remove `google-genai`. Add `openrouter>=1.1.122,<2` and `httpx[socks]>=0.28,<1`; the explicit HTTPX extra supports HTTP/SOCKS proxy transports used by the shared `PROXY` contract. The lockfile is regenerated with `uv`.

## Risks / Trade-offs

- [Configured models do not have ZDR providers] → Startup configuration still validates locally; the provider returns a classified generation error and Telegram flows use their existing safe failure path.
- [OpenRouter SDK response/error shapes change within v1] → Pin below v2, isolate parsing/error mapping, and cover the adapter with fake-SDK tests.
- [SDK retries can extend a single request] → Bound request timeout to 45 seconds and retry elapsed time to 15 seconds.
- [Injected HTTPX client ownership is ambiguous] → Make ownership explicit in `OpenRouterClient` and test idempotent close for direct and proxy transports.
- [Existing active change refers to removed Gemini symbols] → Preserve its files unchanged and document that it cannot be applied until adapted in a separate change.

## Migration Plan

1. Deploy updated code, examples, and a production TOML containing two operator-selected OpenRouter model slugs.
2. Replace `GEMINI_API_KEY` with `OPENROUTER_API_KEY` and `PROXY_URL` with optional `PROXY` in the deployment environment.
3. Run one non-Telegram generation probe that reports only success/category metadata.
4. Start a test configuration containing only two new Telethon accounts; verify one addressed reply and one scheduled A-to-B exchange.
5. Roll back by redeploying the previous application revision together with its previous Gemini environment/TOML contract; configuration versions must move with code versions.

## Open Questions

Production primary/fallback model slugs and the two test Telethon sessions remain operator-supplied deployment inputs. They do not block repository implementation or offline verification.
