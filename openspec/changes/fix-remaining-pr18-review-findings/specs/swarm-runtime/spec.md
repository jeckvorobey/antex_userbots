## ADDED Requirements

### Requirement: Installed runtime includes storage package
The system SHALL include the `storage` Python package in built wheel and source distributions.

#### Scenario: Wheel import succeeds
- **WHEN** the project wheel is installed outside the source checkout
- **THEN** runtime modules importing `storage.sqlite_database` load without `ModuleNotFoundError`

### Requirement: Startup activation rollback
The system SHALL remove and stop a newly activated bot when persistence of its successful startup availability fails.

#### Scenario: Success snapshot write fails
- **WHEN** a bot completes Telegram startup but its available snapshot cannot be stored
- **THEN** the bot is removed from the active pool, its client is stopped, and startup does not retain contradictory active state

### Requirement: Durable global quarantine ordering
The system SHALL persist global quarantine before updating the transient unavailable snapshot and SHALL keep the account disabled in memory regardless of persistence errors.

#### Scenario: Transient snapshot fails for globally unavailable account
- **WHEN** Telegram confirms global messaging unavailability and snapshot persistence fails
- **THEN** durable quarantine has already been attempted before the snapshot error propagates

### Requirement: Reload group readiness retries
The system SHALL retain configured but temporarily unavailable enabled groups as pending and retry their availability checks on later scheduler ticks.

#### Scenario: Pending group recovers
- **WHEN** a newly configured group fails one transient availability check and succeeds later without another file change
- **THEN** a later tick activates it for routing and scheduling

### Requirement: Reconnect validates current groups
The system SHALL validate a replacement client against the current ready group registry rather than the startup-era group snapshot.

#### Scenario: Group changes before reconnect
- **WHEN** reload activates or retargets a group and a bot reconnects afterward
- **THEN** the replacement client completes membership and write checks for that current group before re-entering the active pool

### Requirement: Private invite classification is case insensitive
The system SHALL classify Telegram private invite URLs without depending on scheme or host letter case and SHALL never log their invite hash.

#### Scenario: Uppercase invite URL
- **WHEN** target is `HTTPS://T.ME/+secret_hash`
- **THEN** runtime uses the private-invite flow and logs only a redacted marker
