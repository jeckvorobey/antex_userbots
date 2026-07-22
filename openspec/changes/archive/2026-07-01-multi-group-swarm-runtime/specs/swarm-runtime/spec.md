## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Group runtime registry
The system SHALL maintain runtime state for configured groups separately from immutable configuration.

#### Scenario: Enabled group becomes active after resolve
- **WHEN** at least one active bot resolves an enabled group to a Telegram target and chat id
- **THEN** the group runtime state is available for routing and scheduled exchanges

#### Scenario: Disabled group stops runtime work
- **WHEN** a reload marks a group disabled
- **THEN** routing and scheduling skip that group without stopping the bot pool
