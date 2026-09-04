## ADDED Requirements

### Requirement: Shared proxy transport compatibility
The system SHALL accept a shared proxy only when its scheme is supported by both Telegram and the OpenRouter HTTP transport.

#### Scenario: SOCKS4 proxy is rejected
- **WHEN** `PROXY` uses the `socks4` scheme
- **THEN** settings validation fails before any external client is constructed

#### Scenario: Common proxy schemes remain accepted
- **WHEN** `PROXY` uses `http`, `https`, `socks5`, or `socks5h`
- **THEN** the validated secret value is available to both clients

### Requirement: Reloaded safety limits apply immediately
The system SHALL apply reloaded output-length and mention-count limits to the shared generation client before subsequent publishing work.

#### Scenario: Reload tightens output limits
- **WHEN** TOML reload lowers `max_output_chars` or `max_mentions_per_message`
- **THEN** subsequent reply and scheduled output validation uses the new limits without restart
