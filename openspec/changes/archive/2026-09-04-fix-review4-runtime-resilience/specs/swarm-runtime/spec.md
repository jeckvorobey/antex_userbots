## MODIFIED Requirements

### Requirement: Target group membership
The system SHALL wait a random inclusive 30–60 second delay before each bot's startup membership check, build one reusable dialog index for that bot, resolve or join every enabled configured group during startup, validate new or changed enabled groups for every active bot after reload before activation, and resolve groups during scheduler ticks only through a currently active bot client.

#### Scenario: Startup membership delay stays within the configured range
- **WHEN** an enabled bot reaches either startup membership hook
- **THEN** the runtime waits a random delay from 30 through 60 seconds before the first membership operation

#### Scenario: Multi-group membership reuses one dialog scan
- **WHEN** one bot checks membership for multiple enabled groups during startup
- **THEN** the runtime scans that bot's available dialogs once and reuses the resulting index for every group check

#### Scenario: Unresolved enabled group rejects startup
- **WHEN** an enabled group cannot be resolved or joined for a bot
- **THEN** that bot does not enter the active pool

#### Scenario: Group write permission is required
- **WHEN** group permission lookup returns false or unknown for a bot
- **THEN** the group check fails without creating global account quarantine

#### Scenario: Reloaded group is checked before activation
- **WHEN** reload adds, enables, or changes the identity of an enabled group
- **THEN** every active bot resolves or joins it and confirms `can_write=True` before routing or scheduling activates the group

#### Scenario: Reloaded group check fails
- **WHEN** any active bot cannot resolve, join, or write to a new or changed enabled group
- **THEN** that group remains excluded from routing and scheduling without globally quarantining the bot

#### Scenario: Scheduler resolves through an active client
- **WHEN** the client originally used during startup has been disabled and another bot remains active
- **THEN** the next scheduler tick resolves configured groups through the remaining active bot client

#### Scenario: Scheduler has no active client
- **WHEN** no bot is active when a scheduler tick starts
- **THEN** the tick returns without resolving a group or raising an exception

#### Scenario: Telegram peer namespaces remain isolated
- **WHEN** a user dialog and a channel dialog expose the same raw entity id
- **THEN** group lookup resolves the namespace-aware channel dialog and never returns the user entity

#### Scenario: Positive basic group id resolves to chat namespace
- **WHEN** a configured positive raw id exists in basic-chat, channel, and user namespaces
- **THEN** group lookup checks the basic-chat marked peer before the channel fallback and never returns the user entity

#### Scenario: Already joined target is reused
- **WHEN** the bot already has a matching dialog by chat id or public target for an enabled group
- **THEN** no join request is sent for that group

#### Scenario: Public target can be joined
- **WHEN** the bot is not already in a public target group
- **THEN** the runtime joins the group using the normalized public target and records the resolved entity in the reusable index

#### Scenario: Join update without entity triggers dialog refresh
- **WHEN** Telegram reports a successful group join through an update container without a chat entity
- **THEN** the runtime refreshes joined dialogs and caches the actual group entity instead of the update container

#### Scenario: Private invite link can be joined without chat id
- **WHEN** `group_target` is a private invite link and no `group_chat_id` is required for membership verification
- **THEN** the runtime imports the invite link and records the resolved entity in the reusable index

#### Scenario: Private invite link with unavailable chat id fails clearly
- **WHEN** `group_chat_id` is configured, the bot cannot see that group, and `group_target` is a private invite link
- **THEN** startup raises a clear membership error instead of importing the invite link

### Requirement: Client supervision
The system SHALL keep active bot clients supervised and continue reconnect attempts after unexpected disconnects, client errors, or transient replacement-client startup failures.

#### Scenario: Client error triggers reconnect
- **WHEN** `run_until_disconnected` raises an error
- **THEN** the manager records reconnect state, waits according to backoff, stops the old client when present, and starts the bot again

#### Scenario: Transient replacement startup failure is retried
- **WHEN** a reconnect replacement client fails to start or complete its health checks
- **THEN** the failed replacement is cleaned up and a later supervisor attempt creates another replacement without `KeyError`

#### Scenario: Reconnect discovers globally unavailable account
- **WHEN** the global messaging health-check fails during reconnect
- **THEN** the runtime persistently quarantines and disables the account, removes it from the active pool, and does not schedule another reconnect

#### Scenario: Reconnect checks account before reuse
- **WHEN** a disconnected active bot is reconnecting
- **THEN** it is removed from the active pool before the new client is exposed to the startup health-check and membership hook
