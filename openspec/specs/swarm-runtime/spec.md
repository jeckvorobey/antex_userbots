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

### Requirement: Exclusive swarm runtime ownership
The process MUST acquire an exclusive inter-process runtime lock derived from the effective SQLite path before it opens SQLite connections or starts Telegram clients.

#### Scenario: New container overlaps an active container
- **WHEN** a new container starts while another swarm process holds the runtime lock on the shared persistent volume
- **THEN** the new process waits without opening SQLite or Telegram connections until the old process releases the lock

#### Scenario: Runtime lock is acquired
- **WHEN** no active process holds the runtime lock after the startup handover delay
- **THEN** the process acquires the lock, logs the non-secret lock path, and continues runtime initialization

#### Scenario: Runtime lock path is replaced by a symbolic link
- **WHEN** the runtime lock path resolves to a symbolic link or another non-regular file
- **THEN** startup rejects that path without following it or changing the linked file

#### Scenario: Runtime lock file permissions are normalized
- **WHEN** the process opens an existing regular runtime lock file
- **THEN** it restricts the file mode to owner read and write permissions before acquiring the kernel lock

#### Scenario: Runtime lock wait expires
- **WHEN** another process keeps the runtime lock beyond the bounded startup timeout
- **THEN** startup fails with a clear error before SQLite or Telegram initialization

#### Scenario: In-memory tests do not require a file lock
- **WHEN** the effective SQLite path is `:memory:`
- **THEN** runtime ownership behaves as a no-op and does not create a lock file

### Requirement: Signal-driven graceful shutdown
The process MUST treat `SIGTERM` and `SIGINT` as graceful shutdown requests throughout startup and normal operation.

#### Scenario: Signal during normal supervision
- **WHEN** the process receives a shutdown signal while bot supervision is active
- **THEN** it stops scheduler work, cancels and awaits supervision tasks, disconnects all Telegram clients, closes both SQLite connections, and releases the runtime lock last

#### Scenario: Signal during bot startup
- **WHEN** the process receives a shutdown signal while a Telegram client is in a startup hook
- **THEN** the partially started client is disconnected and the remaining runtime resources are closed before the process exits

#### Scenario: Signal while waiting for ownership
- **WHEN** the process receives a shutdown signal during the handover delay or runtime lock wait
- **THEN** the wait stops promptly and the process exits without opening SQLite or Telegram connections

### Requirement: Complete client cleanup
The swarm manager MUST attempt to stop every created Telegram client during shutdown, including clients that fail or are cancelled before active-pool registration.

#### Scenario: Startup hook fails after client connection
- **WHEN** a client connects but its startup hook fails or is cancelled
- **THEN** that client is disconnected before the error or cancellation propagates

#### Scenario: One client stop fails
- **WHEN** stopping one client raises an error during shutdown
- **THEN** the manager logs the failure and still attempts to stop all remaining clients

### Requirement: Fail-closed Coolify volume identity validation
Before opening SQLite or Telegram connections in the Coolify production path, the process MUST verify that the effective database parent is the expected `/app/data` mount and that a pre-provisioned regular marker matches the non-empty `COOLIFY_RESOURCE_UUID`.

#### Scenario: Correct Coolify volume is mounted
- **WHEN** `/app/data` is present in the Linux mount table and its regular `.coolify-resource-uuid` marker matches `COOLIFY_RESOURCE_UUID`
- **THEN** startup logs successful non-secret volume validation and proceeds to the handover delay and runtime lock

#### Scenario: Production data directory is not a mount point
- **WHEN** the effective database resolves under `/app/data` but `/app/data` is absent from the Linux mount table
- **THEN** startup fails before creating a runtime lock, SQLite file, or Telegram connection

#### Scenario: Volume marker is missing or mismatched
- **WHEN** the production mount marker is absent, empty, a symbolic link, a non-regular file, or does not match `COOLIFY_RESOURCE_UUID`
- **THEN** startup fails without creating or replacing the marker and without opening SQLite or Telegram connections

#### Scenario: Local and in-memory execution
- **WHEN** the database is `:memory:` or its effective parent is outside `/app/data` without Coolify runtime indicators
- **THEN** Coolify volume validation is skipped so local tests and development remain supported

### Requirement: Bounded graceful cleanup
Every graceful-shutdown or partial-startup external-resource cleanup operation MUST have a finite deadline, MUST log timeout/error without secrets, and MUST allow cleanup of the remaining resources before the runtime lock is released.

#### Scenario: Registered Telegram client stop hangs
- **WHEN** one registered client does not complete `stop()` within the client cleanup timeout
- **THEN** the manager logs that bot timeout and still attempts to stop every remaining client

#### Scenario: Cancellation occurs during one client startup
- **WHEN** shutdown cancels a client during startup and that unregistered client does not stop within the client cleanup timeout
- **THEN** startup cleanup times out, manager cleanup continues for registered clients, and application shutdown proceeds

#### Scenario: SQLite resource close hangs
- **WHEN** one persistence resource does not close within its cleanup timeout
- **THEN** the timeout is logged, the other persistence resource is still closed, and the runtime lock is released after both cleanup attempts finish

#### Scenario: Cleanup completes within Coolify grace budget
- **WHEN** all cleanup operations reach either completion or their configured deadlines
- **THEN** the application finishes its internal shutdown budget with margin below the documented production Coolify stop grace period
