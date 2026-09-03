## ADDED Requirements

### Requirement: Bounded OpenRouter completion
The system SHALL bound every OpenRouter Chat Completion to at most 256 generated tokens before provider execution while retaining the stricter publish-time character limit.

#### Scenario: Reply completion is bounded
- **WHEN** `generate_reply` sends an OpenRouter request
- **THEN** the request contains `max_completion_tokens=256`

#### Scenario: Start-topic completion is bounded
- **WHEN** `start_topic` sends an OpenRouter request
- **THEN** the request contains `max_completion_tokens=256`

## MODIFIED Requirements

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
