# Prompt And Gemini Generation

## Purpose

Define prompt loading, persona composition, topic loading, and Gemini generation behavior.

## Requirements

### Requirement: Runtime prompt files
The system SHALL load prompt text from runtime `.md` files rather than hardcoding prompt content.

#### Scenario: Prompt file is loaded by name
- **WHEN** `PromptLoader.load("system")` is called
- **THEN** it reads the full contents of `system.md` from the configured prompts directory

#### Scenario: Missing prompt fails clearly
- **WHEN** the requested prompt file does not exist
- **THEN** `PromptLoader` raises `FileNotFoundError`

### Requirement: Prompt composition
The system SHALL compose generated-task prompts from base prompt, bot persona, and optional exchange context.

#### Scenario: Base prompt and persona are combined
- **WHEN** a base prompt and persona are available
- **THEN** the composed prompt contains the stripped base prompt followed by stripped persona separated by a blank line

#### Scenario: Exchange context is appended
- **WHEN** exchange context is provided
- **THEN** it is appended after base prompt and persona separated by a blank line

#### Scenario: Missing persona file is allowed
- **WHEN** the configured persona file does not exist
- **THEN** prompt composition logs a warning and continues without persona text

#### Scenario: Unsafe persona path is rejected
- **WHEN** `persona_file` is absolute or contains `..`
- **THEN** prompt composition raises `ValueError`

### Requirement: Topic loading
The system SHALL load scheduled exchange topics from the configured topics file.

#### Scenario: Topic file lines become topics
- **WHEN** the topics file contains non-empty non-comment lines
- **THEN** those lines are loaded as available topics

#### Scenario: Comments are ignored
- **WHEN** topic lines start with `#`
- **THEN** they are not included in the topic list

#### Scenario: Empty topic list fails on pick
- **WHEN** no topics are loaded
- **THEN** `pick_random` raises `ValueError` with message `Список тем пуст`

### Requirement: Gemini reply generation
The system SHALL generate replies by sending system instruction, rendered history, and user message to the configured Gemini model.

#### Scenario: Reply request includes history and message
- **WHEN** `generate_reply` is called with history and a user message
- **THEN** the Gemini request contents include rendered history followed by `Пользователь: <message>`

#### Scenario: Start topic request includes topic
- **WHEN** `start_topic` is called
- **THEN** the Gemini request contents include `Тема разговора: <topic>`

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

