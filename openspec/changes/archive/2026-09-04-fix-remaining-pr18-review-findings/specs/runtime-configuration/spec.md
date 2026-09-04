## ADDED Requirements

### Requirement: Shared proxy transport compatibility
The system SHALL accept a shared proxy only when its scheme is supported by both Telegram and the OpenRouter HTTP transport.

#### Scenario: SOCKS4 proxy is rejected
- **WHEN** `PROXY` uses the `socks4` scheme
- **THEN** settings validation fails before any external client is constructed

#### Scenario: Common proxy schemes remain accepted
- **WHEN** `PROXY` uses `http` or `socks5`
- **THEN** the validated secret value is available to both clients

#### Scenario: One transport rejects a proxy scheme
- **WHEN** `PROXY` uses `https`, `socks4`, or `socks5h`
- **THEN** settings validation fails before any external client is constructed

#### Scenario: Rejected proxy contains credentials
- **WHEN** a rejected proxy URL contains username and password
- **THEN** validation and startup logs omit both credential values

### Requirement: Reloaded safety limits apply immediately
The system SHALL apply reloaded output-length and mention-count limits to the shared generation client before subsequent publishing work.

#### Scenario: Reload tightens output limits
- **WHEN** TOML reload lowers `max_output_chars` or `max_mentions_per_message`
- **THEN** subsequent reply and scheduled output validation uses the new limits without restart

### Requirement: Failed reload remains retryable
The settings watcher SHALL advance its observed file signature only after a changed configuration loads successfully.

#### Scenario: Non-atomic TOML write is temporarily invalid
- **WHEN** reload parsing fails for a changed file and the same file signature is checked again
- **THEN** the watcher retries loading rather than treating that signature as applied

### Requirement: Output cap supports mandatory fallbacks
The system SHALL reject `max_output_chars` values smaller than every mandatory local fallback message.

#### Scenario: Output cap is too small
- **WHEN** TOML configures `max_output_chars` below the minimum supported fallback length
- **THEN** settings validation fails before runtime starts
