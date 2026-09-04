## ADDED Requirements

### Requirement: Runtime prompt files
The system SHALL load prompt text from tracked production `.md` files through a non-blocking file cache and a provider-neutral `PromptLoader`.

#### Scenario: Prompt file is loaded safely
- **WHEN** `PromptLoader.load` receives a valid prompt name
- **THEN** it returns cached or freshly read content from the configured prompt directory without blocking the event loop

#### Scenario: Unsafe or missing prompt fails clearly
- **WHEN** the prompt name is empty, absolute, contains a path separator, or names a missing file
- **THEN** `PromptLoader` raises `ValueError` or `FileNotFoundError` before any provider request

### Requirement: Prompt composition and topics
The system SHALL preserve cached persona composition, scheduled group context, topic loading, and normalized topic-key behavior independently of the generation provider.

#### Scenario: Composed prompt includes available context
- **WHEN** base prompt, persona, and exchange context are available
- **THEN** stripped sections are combined in that order with group context included for scheduled exchanges

#### Scenario: Topic selection preserves anti-repeat metadata
- **WHEN** topic intents are loaded from non-comment lines
- **THEN** the selector exposes their cached normalized keys and fails clearly if no topic can be picked

### Requirement: Provider-neutral generation interface
The system SHALL expose `TextGenerationClient` with async `generate_reply`, `start_topic`, and `close` operations plus `is_output_safe` validation.

#### Scenario: Telegram flows use provider-neutral dependency
- **WHEN** reply routing or scheduled orchestration needs generated text
- **THEN** it calls an injected `ai_client` without importing a provider-specific client type

#### Scenario: Generation methods preserve prompt semantics
- **WHEN** reply or start-topic generation is requested
- **THEN** reply history and user text or the selected topic are included in the user context while the composed instruction is sent separately

### Requirement: Strict OpenRouter requests
The system SHALL send non-streaming Chat Completions through the official async OpenRouter SDK using configured model order and strict provider privacy/routing preferences.

#### Scenario: Request contains ordered models and ZDR policy
- **WHEN** either generation method calls OpenRouter
- **THEN** `chat.send_async` receives the configured `models` in order and provider preferences with `zdr=true`, `data_collection="deny"`, `allow_fallbacks=true`, and `require_parameters=true`

#### Scenario: System and redacted user messages are separated
- **WHEN** a request is built
- **THEN** messages contain one `system` instruction followed by one redacted `user` context message

#### Scenario: Optional temperature is omitted
- **WHEN** `[openrouter].temperature` is absent
- **THEN** the SDK request does not contain a temperature argument

#### Scenario: Configured temperature is forwarded
- **WHEN** `[openrouter].temperature` is present
- **THEN** the SDK request contains that exact temperature

### Requirement: OpenRouter retries and errors
The system SHALL use a 45-second request timeout and bounded SDK backoff for connection failures, 408, 429, all 5xx statuses, 524, and 529.

#### Scenario: Retry configuration is bounded
- **WHEN** the OpenRouter client is created
- **THEN** SDK retry backoff starts at 500 ms, caps at 5000 ms, stops after 15000 ms, and adds at most 300 ms jitter

#### Scenario: Temporary provider failure is classified
- **WHEN** SDK transport, timeout, or retryable-status failure remains after retries
- **THEN** the adapter raises `TemporaryGenerationError` without logging raw exception text

#### Scenario: Permanent provider failure is classified
- **WHEN** a non-retryable SDK failure occurs
- **THEN** the adapter raises `GenerationError` without exposing provider payloads or credentials

#### Scenario: Empty response is rejected
- **WHEN** the first response choice has missing, non-text, or whitespace-only content
- **THEN** the adapter raises `GenerationError`

### Requirement: Model fallback
The system SHALL delegate model fallback to OpenRouter by sending the complete configured model list in operator-defined order.

#### Scenario: Primary precedes fallback models
- **WHEN** models are configured as an ordered list
- **THEN** every generation request preserves that order without local per-model retry loops

### Requirement: Generation input redaction
The system SHALL redact obvious secret-like strings and Telegram invite links before sending any history, message, topic, or dynamic context to OpenRouter.

#### Scenario: Sensitive input is redacted before request
- **WHEN** provider-bound context contains an invite link or token-like/session-like string
- **THEN** the SDK receives a placeholder instead of the raw sensitive value

### Requirement: Generation output safety
The system SHALL validate generated output against configured length, invite-link, token-like, and mention limits before Telegram callers publish it.

#### Scenario: Unsafe output is rejected
- **WHEN** generated text violates any configured output rule
- **THEN** `is_output_safe` returns false and the Telegram flow uses its safe local fallback

### Requirement: Safe provider observability
The system SHALL log provider operation categories without logging the API key, proxy credentials, prompts, history, generated text, or raw exception text.

#### Scenario: Proxy log description omits credentials
- **WHEN** `PROXY` contains credentials
- **THEN** logs contain only its scheme, host, and port

#### Scenario: Provider error log is categorical
- **WHEN** an OpenRouter request fails
- **THEN** the log identifies only the operation and safe error category or status

### Requirement: Managed OpenRouter lifecycle
The system SHALL close the SDK transport and any adapter-owned proxy HTTP client exactly once.

#### Scenario: Direct client closes cleanly
- **WHEN** runtime shuts down after direct OpenRouter use
- **THEN** the SDK async lifecycle closes its internally created transport

#### Scenario: Proxy client closes cleanly
- **WHEN** runtime shuts down after proxy OpenRouter use
- **THEN** both the SDK lifecycle and adapter-owned HTTPX client are closed without a second close causing failure

### Requirement: Existing conversational prompt behavior
The system SHALL preserve city-aware openings, important-service questions and answers, non-promotional ordinary replies, and distinctive persona guidance after provider migration.

#### Scenario: Important service behavior is preserved
- **WHEN** generation context is marked as an important service question or answer
- **THEN** existing prompt rules produce a conversational question or a brief answer containing the required Mini App link as applicable

#### Scenario: Ordinary and persona behavior is preserved
- **WHEN** an ordinary reply or scheduled exchange is generated
- **THEN** existing persona, varied-opening, city context, and non-promotional rules remain present in the composed instruction
