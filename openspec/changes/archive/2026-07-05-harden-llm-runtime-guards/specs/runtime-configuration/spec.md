## ADDED Requirements

### Requirement: Runtime security settings
The system SHALL support a dedicated `swarm.security` configuration section for abuse throttling, LLM gating, output safety, and history retention.

#### Scenario: Security defaults are applied
- **WHEN** the TOML omits the `swarm.security` section
- **THEN** settings expose built-in defaults for reply throttling, LLM enablement, output safety, and retention cleanup

#### Scenario: Security overrides are applied
- **WHEN** the TOML provides `swarm.security` override fields
- **THEN** settings expose those overrides as effective runtime security values
