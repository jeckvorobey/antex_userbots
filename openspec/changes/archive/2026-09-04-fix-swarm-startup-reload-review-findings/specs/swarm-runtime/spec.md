## MODIFIED Requirements

### Requirement: Enabled bot startup
The system SHALL start only enabled swarm bot profiles, collect their Telegram user ids, and clean up any client that fails before active-pool registration completes.

#### Scenario: Disabled bot is skipped
- **WHEN** a bot profile has `enabled = false`
- **THEN** the swarm manager does not start a client for that bot

#### Scenario: Started bot becomes active
- **WHEN** an enabled bot starts successfully and returns a Telegram user id
- **THEN** its bot id is added to the active pool and its Telegram user id is added to `swarm_user_ids`

#### Scenario: Startup failure excludes and stops bot
- **WHEN** an enabled bot fails after its Telegram client was created or connected
- **THEN** the client is stopped and removed, the runtime state is marked as error, and the bot is not added to the active pool

### Requirement: Global account messaging eligibility at startup
Before a swarm account is registered as active, the system SHALL perform a non-publishing global messaging API health-check. A confirmed deactivated, revoked, or globally banned account SHALL be disabled, stopped, persistently quarantined, and logged as requiring attention; group-level failures SHALL remain non-global.

#### Scenario: Global messaging check succeeds
- **WHEN** an enabled bot starts and Telegram accepts the non-publishing messaging action
- **THEN** membership checks and normal active-pool registration continue

#### Scenario: Account is globally unavailable
- **WHEN** Telegram returns a confirmed deactivated, revoked, or globally banned account error during connection or the startup messaging check
- **THEN** the client is stopped, the bot is not added to the active pool, global quarantine is saved, and an error log identifies the bot as requiring attention

#### Scenario: Frozen messaging method is rejected
- **WHEN** Telegram returns `FROZEN_METHOD_INVALID` during the non-publishing messaging action
- **THEN** the runtime treats the account as globally unavailable and applies global quarantine

#### Scenario: Global quarantine persistence fails
- **WHEN** the runtime cannot persist global quarantine for a confirmed globally unavailable account
- **THEN** the account remains disabled in memory and startup fails instead of continuing without durable quarantine

#### Scenario: Recipient-specific restriction is not global quarantine
- **WHEN** a group cannot be resolved or does not confirm `can_write=True`
- **THEN** startup rejects that bot without classifying the condition or persisting it as a global account freeze

### Requirement: Fresh availability determines startup pool
The system SHALL replace only the transient startup availability snapshot before checking enabled bot profiles, preserve durable quarantine rows, and admit a profile only after the global Telegram eligibility check and `can_write=True` for every enabled group.

#### Scenario: Startup snapshot is replaced
- **WHEN** startup begins with previous `__startup__` availability rows
- **THEN** those transient rows are removed before fresh results are recorded

#### Scenario: Durable quarantine survives startup reset
- **WHEN** a bot has a quarantine row created for a permanent Telegram send restriction
- **THEN** startup reset preserves that row until an explicit manual removal

### Requirement: Target group membership
The system SHALL wait a random inclusive 30–60 second delay before each bot's startup membership check, build one reusable dialog index for that bot, resolve or join every enabled configured group during startup, and validate new or changed enabled groups for every active bot after reload before activation.

#### Scenario: Startup membership delay stays within the configured range
- **WHEN** an enabled bot reaches either startup membership hook
- **THEN** the runtime waits a random delay from 30 through 60 seconds before the first membership operation

#### Scenario: Multi-group membership reuses one dialog scan
- **WHEN** one bot checks membership for multiple enabled groups during startup
- **THEN** the runtime scans that bot's available dialogs once and reuses the resulting index for every group check

#### Scenario: Telegram peer namespaces remain isolated
- **WHEN** a user dialog and a channel dialog expose the same raw entity id
- **THEN** group lookup resolves the namespace-aware channel dialog and never returns the user entity

#### Scenario: Positive basic group id resolves to chat namespace
- **WHEN** a configured positive raw id exists in basic-chat, channel, and user namespaces
- **THEN** group lookup checks the basic-chat marked peer before the channel fallback and never returns the user entity

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
