## MODIFIED Requirements

### Requirement: Runtime security settings
The system SHALL support a dedicated `swarm.security` configuration section for abuse throttling, pending reply capacity, LLM gating, output safety, and history retention.

#### Scenario: Security defaults are applied
- **WHEN** the TOML omits the `swarm.security` section
- **THEN** settings expose safe code defaults including a positive per-bot pending reply limit

#### Scenario: Security overrides are loaded
- **WHEN** the TOML provides `swarm.security` override fields including `addressed_reply_max_pending_per_bot`
- **THEN** settings expose those overrides as effective runtime security values
