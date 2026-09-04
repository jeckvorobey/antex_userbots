## MODIFIED Requirements

### Requirement: Target group membership
The system SHALL wait a random inclusive 30–60 second delay before each bot's startup membership check, then resolve or join every enabled configured group for that bot during startup and after group reload.

#### Scenario: Startup membership delay stays within the configured range
- **WHEN** an enabled bot reaches either startup membership hook
- **THEN** the runtime waits a random delay from 30 through 60 seconds before the first membership operation

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
