## MODIFIED Requirements

### Requirement: Target group membership
The system SHALL wait a random inclusive 30–60 second delay before each bot's startup membership check, build one reusable dialog index for that bot, then resolve or join every enabled configured group for that bot during startup and after group reload.

#### Scenario: Startup membership delay stays within the configured range
- **WHEN** an enabled bot reaches either startup membership hook
- **THEN** the runtime waits a random delay from 30 through 60 seconds before the first membership operation

#### Scenario: Multi-group membership reuses one dialog scan
- **WHEN** one bot checks membership for multiple enabled groups during startup
- **THEN** the runtime scans that bot's available dialogs once and reuses the resulting index for every group check

#### Scenario: Telegram peer namespaces remain isolated
- **WHEN** a user dialog and a channel dialog expose the same raw entity id
- **THEN** group lookup resolves the namespace-aware channel dialog and never returns the user entity

#### Scenario: Already joined target is reused
- **WHEN** the bot already has a matching dialog by chat id or public target for an enabled group
- **THEN** no join request is sent for that group

#### Scenario: Public target can be joined
- **WHEN** the bot is not already in a public target group
- **THEN** the runtime joins the group using the normalized public target and records the resolved entity in the reusable index

#### Scenario: Private invite link can be joined without chat id
- **WHEN** `group_target` is a private invite link and no `group_chat_id` is required for membership verification
- **THEN** the runtime imports the invite link and records the resolved entity in the reusable index

#### Scenario: Private invite link with unavailable chat id fails clearly
- **WHEN** `group_chat_id` is configured, the bot cannot see that group, and `group_target` is a private invite link
- **THEN** startup raises a clear membership error instead of importing the invite link

## ADDED Requirements

### Requirement: Per-group target cache
The system SHALL cache resolved Telegram group entities independently by normalized group identity for each client.

#### Scenario: Different groups retain independent cached entities
- **WHEN** the runtime resolves two different configured groups for the same client
- **THEN** resolving either group again returns its own cached entity without another dialog scan

#### Scenario: Changed target does not reuse stale entity
- **WHEN** a settings reload changes the chat id or public target used for a group
- **THEN** the runtime resolves the new identity instead of returning the entity cached for the previous identity
