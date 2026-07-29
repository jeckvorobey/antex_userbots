# Prompt And Gemini Generation

## Purpose

Define prompt loading, persona composition, topic loading, and Gemini generation behavior.
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
- **WHEN** Gemini composes a reply or scheduled exchange with a production persona
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

### Requirement: Gemini reply generation
The system SHALL generate replies by sending system instruction, rendered history, and user message to the configured Gemini model.

#### Scenario: Reply request includes history and message
- **WHEN** `generate_reply` is called with history and a user message
- **THEN** the Gemini request contents include rendered history followed by `Пользователь: <message>`

#### Scenario: Start topic request includes topic
- **WHEN** `start_topic` is called
- **THEN** the Gemini request contents include `Тема разговора: <topic>`

#### Scenario: Start topic adapts intent to group city
- **WHEN** scheduled start-topic generation is composed for a group
- **THEN** the system instruction includes rules to transform the shared topic intent into one natural question for that group's city and not mention another city

#### Scenario: Start topic uses human opening variants
- **WHEN** scheduled start-topic generation is composed
- **THEN** the prompt instructs Gemini to begin like an ordinary chat participant using `привет`, `всем привет`, `здравствуйте`, or by asking the question directly without an introductory word

### Requirement: Gemini resilience
The system SHALL retry temporary Gemini failures and optionally switch to a fallback model.

#### Scenario: Temporary server error is retried
- **WHEN** Gemini raises a temporary status such as 503 before retry limit is reached
- **THEN** the client waits using exponential backoff and retries

#### Scenario: Retry limit raises temporary error
- **WHEN** temporary failures continue through the configured retry limit without fallback success
- **THEN** `GeminiTemporaryError` is raised

#### Scenario: Fallback model is used
- **WHEN** the primary model exhausts retry attempts and a distinct fallback model is configured
- **THEN** the client attempts generation with the fallback model

#### Scenario: Request timeout is temporary
- **WHEN** a Gemini request times out
- **THEN** it is treated as a temporary error and retried while attempts remain

### Requirement: Safe proxy reporting
The system SHALL avoid exposing proxy credentials in Gemini logs.

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
The system SHALL generate important-service responder messages as short natural chat replies that mention `https://t.me/tt_exchenge_bot/antex`.

#### Scenario: Important answer mentions required miniapp link
- **WHEN** reply generation receives exchange context marked `important_service_answer`
- **THEN** the generated answer naturally mentions `https://t.me/tt_exchenge_bot/antex`

#### Scenario: Important answer varies wording
- **WHEN** important-service answers are generated for repeated service scenarios
- **THEN** the prompt instructs Gemini to avoid copying a fixed advertising sentence and to vary wording in a similar conversational style

#### Scenario: Important answer stays brief
- **WHEN** reply generation receives exchange context marked `important_service_answer`
- **THEN** the generated answer is constrained to one or two short conversational sentences

### Requirement: Ordinary prompt behavior remains non-promotional
The system SHALL keep ordinary scheduled exchanges and addressed replies from automatically becoming service advertisements.

#### Scenario: Ordinary start topic has no important marker
- **WHEN** start-topic generation receives ordinary exchange context without `important_service_question`
- **THEN** the prompt treats the topic as a normal city-aware conversation intent and does not require service promotion

#### Scenario: Ordinary reply has no important marker
- **WHEN** reply generation receives ordinary exchange context without `important_service_answer`
- **THEN** the prompt does not require mentioning `https://t.me/tt_exchenge_bot/antex`

### Requirement: Gemini input redaction
The system SHALL redact obvious secret-like and invite-link content before sending prompts to Gemini.

#### Scenario: Invite link is redacted before request
- **WHEN** reply history or user input contains a Telegram invite link
- **THEN** the Gemini request uses a redacted placeholder instead of the raw invite link

#### Scenario: Token-like string is redacted before request
- **WHEN** reply history or user input contains an obvious token-like or session-like secret string
- **THEN** the Gemini request uses a redacted placeholder instead of the raw secret

### Requirement: Gemini output safety validation
The system SHALL validate generated output against runtime safety rules before publish-time callers accept it.

#### Scenario: Too-long output is rejected
- **WHEN** the generated output exceeds the configured maximum length
- **THEN** the output validator marks it unsafe

#### Scenario: Forbidden pattern output is rejected
- **WHEN** the generated output contains blocked invite-link, token-like, or excessive-mention patterns
- **THEN** the output validator marks it unsafe
