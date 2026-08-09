## MODIFIED Requirements

### Requirement: Enabled bot startup
The system SHALL start only enabled swarm bot profiles, build a fresh startup
availability snapshot for them, and collect Telegram user ids only for profiles
that pass all startup eligibility checks.

#### Scenario: Disabled bot is skipped
- **WHEN** a bot profile has `enabled = false`
- **THEN** the swarm manager does not start a client for that bot

#### Scenario: Started bot becomes active
- **WHEN** an enabled bot passes global account and every enabled-group write-permission check and returns a Telegram user id
- **THEN** its bot id is added to the active pool and its Telegram user id is added to `swarm_user_ids`

#### Scenario: Startup failure excludes bot
- **WHEN** an enabled bot fails startup eligibility or client startup
- **THEN** the bot runtime state is marked as error or disabled, a fresh unavailable result is persisted, and it is not added to the active pool

### Requirement: Minimum active bot count
The system SHALL require at least two enabled bots before startup and at least
two active bots after fresh availability checks complete.

#### Scenario: Fewer than two enabled bots
- **WHEN** swarm mode is started with fewer than two enabled bot profiles
- **THEN** startup fails

#### Scenario: Fewer than two active bots after startup
- **WHEN** fresh startup availability checks leave fewer than two active bots
- **THEN** the orchestrator job is not registered and startup fails
