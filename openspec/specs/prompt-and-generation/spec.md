# Prompt And Text Generation

## Purpose

Define provider-neutral prompt loading, persona composition, topic loading, safety, and OpenRouter generation behavior.
## Requirements
### Requirement: Runtime prompt files
The system SHALL load prompt text from tracked production `.md` files through a non-blocking file cache rather than hardcoding prompt content or blocking the event loop for repeated reads.

#### Scenario: Prompt file is loaded by name
- **WHEN** `PromptLoader.load("system")` is called
- **THEN** it returns the full contents of `system.md` from the configured prompts directory

#### Scenario: Unchanged prompt uses cached text
- **WHEN** the same prompt file is loaded again without a file signature change
- **THEN** the cached text is returned without reading the file contents again

#### Scenario: Changed prompt is refreshed
- **WHEN** a cached prompt file changes its modification timestamp or size
- **THEN** the next load reads and caches the new contents

#### Scenario: File IO stays outside the event loop
- **WHEN** prompt or persona metadata and contents are read
- **THEN** blocking filesystem operations execute outside the asyncio event loop

#### Scenario: Missing prompt fails clearly
- **WHEN** the requested prompt file does not exist
- **THEN** `PromptLoader` raises `FileNotFoundError`

#### Scenario: Unsafe prompt name is rejected
- **WHEN** a prompt name is empty, absolute, or contains a path separator
- **THEN** `PromptLoader` raises `ValueError` before accessing the filesystem

#### Scenario: Prompt examples are not required
- **WHEN** repository prompt files are validated
- **THEN** runtime prompt names such as `system.md`, `reply.md`, `start_topic.md`, `topics.md`, and `wind_down_hint.md` exist without requiring matching `*.example.md` files

### Requirement: Prompt composition
The system SHALL compose generated-task prompts from base prompt, cached bot persona, and optional exchange context including scheduled group context.

#### Scenario: Base prompt and persona are combined
- **WHEN** a base prompt and persona are available
- **THEN** the composed prompt contains the stripped base prompt followed by stripped persona separated by a blank line

#### Scenario: Unchanged persona uses cached text
- **WHEN** the same validated persona file is composed again without a file signature change
- **THEN** cached persona text is reused

#### Scenario: Changed persona is refreshed
- **WHEN** a cached persona file changes its modification timestamp or size
- **THEN** the next composition includes the new persona contents

#### Scenario: Exchange context is appended
- **WHEN** exchange context is provided
- **THEN** it is appended after base prompt and persona separated by a blank line

#### Scenario: Scheduled group context is appended
- **WHEN** scheduled exchange composition receives group city or group id context
- **THEN** that context is included in the exchange context passed to prompt composition

#### Scenario: Missing persona file is allowed
- **WHEN** the configured persona file does not exist
- **THEN** prompt composition logs a warning and continues without persona text

#### Scenario: Unsafe persona path is rejected
- **WHEN** `persona_file` is absolute or contains `..`
- **THEN** prompt composition raises `ValueError`

### Requirement: Persona overlays provide distinctive human behavior guidance
The system SHALL use production persona overlays that describe each character as a distinct living chat participant rather than a short generic assistant-like template.

#### Scenario: Persona keeps base identity
- **WHEN** a production persona profile is expanded
- **THEN** it preserves the character name, base role as a living chat participant, and existing high-level instruction not to mention AI or bot identity

#### Scenario: Persona guides varied replies
- **WHEN** AI client composes a reply or scheduled exchange with a production persona
- **THEN** the persona overlay includes guidance for variable message length, questions, humor, disagreement, silence, and non-deterministic behavior

#### Scenario: Persona avoids identical output patterns
- **WHEN** production persona guidance is used across multiple bots
- **THEN** it instructs each character not to copy other characters' style or reuse identical constructions

### Requirement: Topic loading
The system SHALL load scheduled exchange topic intents from the configured topics file.

#### Scenario: Topic file lines become topic intents
- **WHEN** the topics file contains non-empty non-comment lines
- **THEN** those lines are loaded as available topic intents

#### Scenario: Comments are ignored
- **WHEN** topic lines start with `#`
- **THEN** they are not included in the topic list

#### Scenario: Empty topic list fails on pick
- **WHEN** no topics are loaded
- **THEN** `pick_random` raises `ValueError` with message `Список тем пуст`

#### Scenario: Topic intents are city-neutral
- **WHEN** the committed shared topics file is validated
- **THEN** topic intent lines do not contain fixed city names from configured groups or old single-city prompts

### Requirement: Topic key caching
The system SHALL cache normalized keys for loaded scheduled exchange topic intents.

#### Scenario: Topic selector caches normalized key
- **WHEN** `TopicSelector.load` reads a topic intent
- **THEN** `TopicSelector.topic_key(topic)` returns the normalized key without requiring callers to recompute it

#### Scenario: Orchestrator uses cached topic key when available
- **WHEN** scheduled topic anti-repeat evaluates topics from a `TopicSelector`
- **THEN** it uses the selector-provided topic key for recent-topic comparison

#### Scenario: Orchestrator preserves fallback for simple selectors
- **WHEN** scheduled topic anti-repeat receives a selector without `topic_key`
- **THEN** it falls back to normalizing the topic text directly

### Requirement: Provider-neutral generation interface
The system SHALL expose an async `TextGenerationClient` with `generate_reply`, `start_topic`, `close`, and `is_output_safe` operations, and Telegram flows SHALL depend on it as `ai_client`.

#### Scenario: Reply request separates instruction and user context
- **WHEN** `generate_reply` is called with history and a user message
- **THEN** the request contains one system message and one redacted user message with rendered history followed by `Пользователь: <message>`

#### Scenario: Start topic request includes topic
- **WHEN** `start_topic` is called
- **THEN** the redacted user message contains `Тема разговора: <topic>`

#### Scenario: Start topic adapts intent to group city
- **WHEN** scheduled start-topic generation is composed for a group
- **THEN** the system instruction includes rules to transform the shared topic intent into one natural question for that group's city and not mention another city

#### Scenario: Start topic uses human opening variants
- **WHEN** scheduled start-topic generation is composed
- **THEN** the prompt instructs the AI client to begin like an ordinary chat participant using `привет`, `всем привет`, `здравствуйте`, or by asking the question directly without an introductory word

### Requirement: Strict OpenRouter requests
The system SHALL send non-streaming Chat Completions through the official async OpenRouter SDK with ordered models and strict provider privacy preferences.

#### Scenario: Request contains ordered models and ZDR policy
- **WHEN** either generation method calls OpenRouter
- **THEN** `chat.send_async` receives configured `models` in order and provider preferences with `zdr=true`, `data_collection="deny"`, `allow_fallbacks=true`, and `require_parameters=true`

#### Scenario: Optional temperature is omitted
- **WHEN** `[openrouter].temperature` is absent
- **THEN** the SDK request omits the temperature argument

#### Scenario: Configured temperature is forwarded
- **WHEN** `[openrouter].temperature` is present
- **THEN** the SDK request contains that exact value

### Requirement: Bounded OpenRouter completion
The system SHALL bound every OpenRouter Chat Completion to at most 256 generated tokens before provider execution while retaining the stricter publish-time character limit.

#### Scenario: Reply completion is bounded
- **WHEN** `generate_reply` sends an OpenRouter request
- **THEN** the request contains `max_completion_tokens=256`

#### Scenario: Start-topic completion is bounded
- **WHEN** `start_topic` sends an OpenRouter request
- **THEN** the request contains `max_completion_tokens=256`

### Requirement: OpenRouter resilience and model fallback
The system SHALL use a 45-second timeout and bounded SDK retries for connection failures, 408, 429, all 5xx statuses, 524, and 529 while delegating ordered model fallback to OpenRouter.

#### Scenario: Retry configuration is bounded
- **WHEN** the client is created
- **THEN** exponential backoff starts at 500 ms, caps at 5000 ms, stops after 15000 ms, and adds at most 300 ms jitter

#### Scenario: Temporary failure is classified
- **WHEN** a retryable transport or status failure remains after SDK retries
- **THEN** `TemporaryGenerationError` is raised without raw provider details

#### Scenario: Permanent or empty response fails safely
- **WHEN** a non-retryable SDK failure or missing non-empty first-choice text occurs
- **THEN** `GenerationError` is raised without raw provider details

#### Scenario: Model order is preserved
- **WHEN** primary and fallback models are configured
- **THEN** every request sends the complete list in operator-defined order without local per-model loops

### Requirement: Safe proxy reporting
The system SHALL avoid exposing proxy credentials in AI client logs.

#### Scenario: Proxy description redacts credentials
- **WHEN** a proxy URL with credentials is configured
- **THEN** log-facing proxy description contains only scheme, host, and port

### Requirement: Important service start-topic prompt behavior
The system SHALL generate important-service initiator messages as ordinary conversational questions based on the selected scenario intent.

#### Scenario: Important question does not mention bot contact
- **WHEN** start-topic generation receives exchange context marked `important_service_question`
- **THEN** the generated question is a single short conversational question and does not mention `https://t.me/tt_exchenge_bot/antex`

#### Scenario: Important question keeps scenario meaning
- **WHEN** the selected important-service scenario is `booking_airbnb`
- **THEN** the generated question asks naturally about booking or paying for Airbnb with RUB or USDT without exposing the internal scenario key

### Requirement: Important service reply prompt behavior
The system SHALL generate important-service responder messages as short natural chat replies that mention `https://t.me/tt_exchenge_bot/antex`, including when external generation is disabled or rejected by output safety validation.

#### Scenario: Important answer mentions required miniapp link
- **WHEN** reply generation receives exchange context marked `important_service_answer`
- **THEN** the generated answer naturally mentions `https://t.me/tt_exchenge_bot/antex`

#### Scenario: Important answer varies wording
- **WHEN** important-service answers are generated for repeated service scenarios
- **THEN** the prompt instructs AI client to avoid copying a fixed advertising sentence and to vary wording in a similar conversational style

#### Scenario: Important answer stays brief
- **WHEN** reply generation receives exchange context marked `important_service_answer`
- **THEN** the generated answer is constrained to one or two short conversational sentences

#### Scenario: Important answer uses a safe local fallback
- **WHEN** scheduled LLM use is disabled or an important-service responder output fails safety validation
- **THEN** runtime uses a short local fallback containing the exact approved URL `https://t.me/tt_exchenge_bot/antex`

### Requirement: Ordinary prompt behavior remains non-promotional
The system SHALL keep ordinary scheduled exchanges and addressed replies from automatically becoming service advertisements.

#### Scenario: Ordinary start topic has no important marker
- **WHEN** start-topic generation receives ordinary exchange context without `important_service_question`
- **THEN** the prompt treats the topic as a normal city-aware conversation intent and does not require service promotion

#### Scenario: Ordinary reply has no important marker
- **WHEN** reply generation receives ordinary exchange context without `important_service_answer`
- **THEN** the prompt does not require mentioning `https://t.me/tt_exchenge_bot/antex`

### Requirement: Generation input redaction
The system SHALL redact obvious secret-like content, private invite links, and URLs containing embedded credentials before sending prompts to the AI provider.

#### Scenario: Invite link is redacted before request
- **WHEN** reply history or user input contains a Telegram invite link
- **THEN** the AI client request uses a redacted placeholder instead of the raw invite link

#### Scenario: Token-like string is redacted before request
- **WHEN** reply history or user input contains an obvious token-like or session-like secret string
- **THEN** the AI client request uses a redacted placeholder instead of the raw secret

#### Scenario: URL credentials are redacted before request
- **WHEN** reply history, user input, or topic contains an HTTP or HTTPS URL with username or password userinfo
- **THEN** the AI client request replaces the complete credential-bearing URL with a redacted placeholder

### Requirement: Generation output safety validation
The system SHALL validate generated output against runtime safety rules and an explicit URL allowlist before publish-time callers accept it.

#### Scenario: Too-long output is rejected
- **WHEN** the generated output exceeds the configured maximum length
- **THEN** the output validator marks it unsafe

#### Scenario: Forbidden pattern output is rejected
- **WHEN** the generated output contains blocked invite-link, token-like, or excessive-mention patterns
- **THEN** the output validator marks it unsafe

#### Scenario: Unapproved external URL is rejected
- **WHEN** generated output contains an HTTP or HTTPS URL outside the approved output URL allowlist
- **THEN** the output validator marks it unsafe

#### Scenario: Approved Mini App URL is accepted
- **WHEN** otherwise safe generated output contains the exact approved Mini App URL `https://t.me/tt_exchenge_bot/antex`
- **THEN** the output validator does not reject it because of that URL

### Requirement: Managed OpenRouter lifecycle
The system SHALL close the SDK transport and any adapter-owned proxy HTTP client exactly once.

#### Scenario: Direct transport closes
- **WHEN** runtime shuts down after direct OpenRouter use
- **THEN** the SDK async lifecycle closes its internal transport once

#### Scenario: Proxy transport closes
- **WHEN** runtime shuts down after proxied OpenRouter use
- **THEN** the SDK lifecycle and adapter-owned HTTPX client each close once

### Requirement: Safe provider observability
The system SHALL log only safe operation categories, model count, status, and credential-free proxy description.

#### Scenario: Provider failure hides sensitive details
- **WHEN** a provider request fails with a raw payload or exception
- **THEN** logs and the raised exception chain omit keys, proxy credentials, prompts, history, generated text, and raw provider text

### Requirement: Important service scenarios are file-backed
The system SHALL load important-service question and answer intent text from tracked prompt files through `PromptLoader` rather than embedding model instructions in Python.

#### Scenario: Scenario prompt is composed
- **WHEN** an important-service exchange is selected
- **THEN** its question and answer intent comes from the cached tracked prompt resource

#### Scenario: Service prompt directives are maintained
- **WHEN** important-service wording, style, or approved-contact instructions change
- **THEN** they are edited in tracked prompt resources without changing Python prompt literals

### Requirement: OpenRouter owned transport always closes
The system SHALL attempt to close its owned HTTP transport even when OpenRouter SDK shutdown raises.

#### Scenario: SDK exit fails
- **WHEN** the SDK `__aexit__` raises during adapter shutdown
- **THEN** HTTPX `aclose` is awaited and the original SDK exception propagates

### Requirement: Prompt redaction covers credential URI schemes
The system SHALL redact credentials embedded in any URI scheme before user text or history is sent to the AI provider.

#### Scenario: SOCKS credentials appear in prompt input
- **WHEN** prompt input contains `socks5://user:password@host:port`
- **THEN** both username and password are replaced by the credential-URL marker

### Requirement: Output safety rejects openable non-allowlisted links
The system SHALL reject Telegram deep links and scheme-less domain links in generated output unless the complete URL is explicitly allowlisted.

#### Scenario: Telegram deep link is generated
- **WHEN** output contains a `tg://` link
- **THEN** output safety rejects it

#### Scenario: Scheme-less domain is generated
- **WHEN** output contains a `www.example.com`-style link
- **THEN** output safety rejects it
