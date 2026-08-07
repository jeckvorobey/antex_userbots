## ADDED Requirements

### Requirement: Global account messaging eligibility at startup
Before a swarm account is registered as active, the system SHALL perform a non-publishing global messaging API health-check. A confirmed deactivated, revoked, or globally banned account SHALL be disabled, stopped, persistently quarantined, and logged as requiring attention.

#### Scenario: Global messaging check succeeds
- **WHEN** an enabled bot starts and Telegram accepts the non-publishing messaging action
- **THEN** membership checks and normal active-pool registration continue

#### Scenario: Account is globally unavailable
- **WHEN** Telegram returns a confirmed deactivated, revoked, or globally banned account error during connection or the startup messaging check
- **THEN** the client is stopped, the bot is not added to the active pool, global quarantine is saved, and an error log identifies the bot as requiring attention

#### Scenario: Recipient-specific restriction is not global quarantine
- **WHEN** a recipient or group does not permit writing
- **THEN** startup does not classify that recipient-specific condition as a global account freeze
