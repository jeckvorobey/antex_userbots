## MODIFIED Requirements

### Requirement: Addressed reply abuse throttling
The system SHALL rate-limit addressed human replies before any external generation call, bound pending replies per bot, and remove expired in-memory rate-limit state.

#### Scenario: Burst sender is throttled
- **WHEN** the same sender exceeds the configured addressed-reply limit for the same bot and chat inside the configured window
- **THEN** the router returns `false`, sends no Telegram response, and skips the AI request

#### Scenario: Sender under the limit is processed
- **WHEN** the sender stays within the configured addressed-reply rate limit
- **THEN** the router continues normal addressed reply processing

#### Scenario: Pending reply capacity is exhausted
- **WHEN** the current bot already has the configured maximum accepted unfinished replies
- **THEN** the router returns `false` and skips history, prompt, AI, delay, and Telegram reply work for the new event

#### Scenario: Pending capacity is released
- **WHEN** accepted reply processing succeeds, fails, or is cancelled
- **THEN** the router releases that pending slot

#### Scenario: Expired sender state is removed
- **WHEN** all timestamps for a rate-limit key are older than the active window during cleanup
- **THEN** timestamps and their chat/sender/bot key are removed from memory

### Requirement: Addressed reply LLM gate
The system SHALL support disabling external LLM usage for addressed human replies through runtime configuration.

#### Scenario: Reply LLM is disabled
- **WHEN** reply LLM usage is disabled in runtime security settings
- **THEN** the router sends a safe local fallback and skips the AI request

### Requirement: Addressed reply output safety
The system SHALL validate generated reply text before publishing it to Telegram.

#### Scenario: Unsafe reply output is replaced
- **WHEN** the AI client returns text that violates configured output safety rules
- **THEN** the router sends a safe fallback instead of unsafe model output
