## ADDED Requirements

### Requirement: Addressed reply abuse throttling
The system SHALL rate-limit addressed human replies before any external LLM call is made.

#### Scenario: Burst sender is throttled
- **WHEN** the same sender exceeds the configured addressed-reply limit for the same bot in the same chat inside the configured time window
- **THEN** the router returns `false`, sends no Telegram response, and skips the Gemini request

#### Scenario: Sender under the limit is processed
- **WHEN** the sender stays within the configured addressed-reply rate limit
- **THEN** the router continues normal addressed reply processing

### Requirement: Addressed reply LLM gate
The system SHALL support disabling external LLM usage for addressed human replies through runtime configuration.

#### Scenario: Reply LLM is disabled
- **WHEN** reply LLM usage is disabled in runtime security settings
- **THEN** the router sends a safe local fallback response and skips the Gemini request

### Requirement: Addressed reply output safety
The system SHALL validate generated reply text before publishing it to Telegram.

#### Scenario: Unsafe reply output is replaced
- **WHEN** Gemini returns reply text that violates the configured output safety rules
- **THEN** the router sends a safe fallback response instead of the unsafe model output
