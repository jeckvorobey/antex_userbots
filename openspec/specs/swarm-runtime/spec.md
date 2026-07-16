# Swarm Runtime

## Purpose

Define how enabled Telegram userbot accounts are started, supervised, registered for routing, and connected to the target group.

## Requirements

### Requirement: Runtime context initialization
The system SHALL initialize shared runtime dependencies before starting swarm clients.

#### Scenario: Runtime dependencies are created
- **WHEN** the application starts
- **THEN** message history and exchange store SQLite tables are initialized, prompt loading is configured, Gemini client is configured, topics are loaded, and prompt composer is created

### Requirement: Enabled bot startup
The system SHALL start only enabled swarm bot profiles and collect their Telegram user ids.

#### Scenario: Disabled bot is skipped
- **WHEN** a bot profile has `enabled = false`
- **THEN** the swarm manager does not start a client for that bot

#### Scenario: Started bot becomes active
- **WHEN** an enabled bot starts successfully and returns a Telegram user id
- **THEN** its bot id is added to the active pool and its Telegram user id is added to `swarm_user_ids`

#### Scenario: Startup failure excludes bot
- **WHEN** an enabled bot fails during startup
- **THEN** the bot runtime state is marked as error and it is not added to the active pool

### Requirement: Minimum active bot count
The system SHALL require at least two enabled bots before startup and at least two active bots after startup.

#### Scenario: Fewer than two enabled bots
- **WHEN** swarm mode is started with fewer than two enabled bot profiles
- **THEN** startup fails

#### Scenario: Fewer than two active bots after startup
- **WHEN** startup leaves fewer than two active bots
- **THEN** the orchestrator job is not registered and startup fails

### Requirement: Handler registration per active bot
The system SHALL register an addressed-reply handler for each active bot client.

#### Scenario: Active bot gets handler
- **WHEN** Telethon events are available and a bot is active
- **THEN** a `NewMessage` handler is registered for that bot client

#### Scenario: Missing active profile is skipped
- **WHEN** an active bot id has no matching enabled profile
- **THEN** handler registration skips that bot id

### Requirement: Target group membership
The system SHALL resolve or join every enabled configured group for each bot during startup and after group reload.

#### Scenario: Already joined target is reused
- **WHEN** the bot already has a matching dialog by chat id or public target for an enabled group
- **THEN** no join request is sent for that group

#### Scenario: Public target can be joined
- **WHEN** the bot is not already in a public target group
- **THEN** the runtime joins the group using the normalized public target

#### Scenario: Private invite link can be joined without chat id
- **WHEN** `group_target` is a private invite link and no `group_chat_id` is required for membership verification
- **THEN** the runtime imports the invite link

#### Scenario: Private invite link with unavailable chat id fails clearly
- **WHEN** `group_chat_id` is configured, the bot cannot see that group, and `group_target` is a private invite link
- **THEN** startup raises a clear membership error instead of importing the invite link

### Requirement: Group runtime registry
The system SHALL maintain runtime state for configured groups separately from immutable configuration.

#### Scenario: Enabled group becomes active after resolve
- **WHEN** at least one active bot resolves an enabled group to a Telegram target and chat id
- **THEN** the group runtime state is available for routing and scheduled exchanges

#### Scenario: Disabled group stops runtime work
- **WHEN** a reload marks a group disabled
- **THEN** routing and scheduling skip that group without stopping the bot pool

### Requirement: Group orchestrator reuse
The system SHALL reuse per-group scheduled orchestrators across scheduler ticks while the group's effective runtime signature is unchanged.

#### Scenario: Unchanged group reuses orchestrator
- **WHEN** two scheduler ticks run for the same enabled group without settings or resolved target changes
- **THEN** the second tick reuses the existing `SwarmOrchestrator` instance for that group

#### Scenario: Changed group rebuilds orchestrator
- **WHEN** a group's effective schedule, target, city, max turns, or skip-human-activity setting changes
- **THEN** the next scheduler tick creates a replacement `SwarmOrchestrator` for that group

#### Scenario: Disabled group cache is pruned
- **WHEN** a reload removes or disables a group
- **THEN** the scheduler cache removes that group's orchestrator and stops ticking it

### Requirement: Client supervision
The system SHALL keep active bot clients supervised and reconnect after unexpected disconnects or client errors.

#### Scenario: Client error triggers reconnect
- **WHEN** `run_until_disconnected` raises an error
- **THEN** the manager records reconnect state, waits according to backoff, stops the old client, and starts the bot again

### Requirement: Human work has priority
The system SHALL prioritize human reply processing over scheduled tasks for the same bot.

#### Scenario: Human slot blocks scheduled slot
- **WHEN** a human reply owns or is waiting for a bot slot
- **THEN** a scheduled task for that bot receives `acquired = false`

### Requirement: Private targets are redacted in logs
The system SHALL not log private Telegram invite hashes.

#### Scenario: Invite link resolve is skipped with redacted log
- **WHEN** group resolution receives a private invite link
- **THEN** direct `get_entity` is skipped and logs contain a redacted marker instead of the invite hash
