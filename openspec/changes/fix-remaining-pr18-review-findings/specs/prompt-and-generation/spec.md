## ADDED Requirements

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
