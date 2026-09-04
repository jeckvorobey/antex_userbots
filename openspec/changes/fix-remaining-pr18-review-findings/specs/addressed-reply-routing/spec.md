## ADDED Requirements

### Requirement: Delayed reply publish eligibility
The system SHALL revalidate both group and bot eligibility immediately before publishing a delayed addressed reply.

#### Scenario: Group disabled during delay
- **WHEN** an addressed reply was accepted but its group leaves the enabled allowlist before publish time
- **THEN** no Telegram reply is sent

#### Scenario: Bot disabled during delay
- **WHEN** an addressed reply was accepted but its bot leaves the active pool before publish time
- **THEN** no Telegram reply is sent

### Requirement: Handler-safe runtime disable
The system SHALL remove a permanently forbidden bot from scheduling immediately while deferring its physical client disconnect until the current Telegram event handler yields.

#### Scenario: Permanent error in reply handler
- **WHEN** `event.reply` raises a permanent Telegram send error
- **THEN** runtime-disable logging, return behavior, and quarantine error propagation complete before client stop runs
