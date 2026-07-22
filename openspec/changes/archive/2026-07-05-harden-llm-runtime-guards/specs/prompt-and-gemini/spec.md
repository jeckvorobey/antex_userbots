## ADDED Requirements

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
