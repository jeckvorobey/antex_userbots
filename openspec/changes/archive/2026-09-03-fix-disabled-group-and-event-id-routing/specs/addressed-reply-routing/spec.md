## MODIFIED Requirements

### Requirement: Ignore non-addressed messages
The system SHALL ignore incoming events that are outside enabled configured groups or are not addressed replies to the current bot, SHALL reject non-reply events before resolving the Telegram sender entity, and SHALL normalize configured group identifiers into the same marked peer-id namespace used by Telethon events.

#### Scenario: Unknown group is ignored
- **WHEN** an incoming event chat id is not one of the enabled configured groups
- **THEN** the addressed reply router returns `false` and sends no response

#### Scenario: Empty allowlist rejects every group
- **WHEN** no enabled configured group has been resolved to a numeric chat id
- **THEN** the addressed reply router rejects every incoming event instead of disabling group filtering

#### Scenario: Target-only group is resolved before handler registration
- **WHEN** an enabled group is configured only with `group_target`
- **THEN** runtime resolves its numeric chat id and adds that id to the shared allowlist before registering addressed-reply handlers

#### Scenario: Positive raw group id is normalized
- **WHEN** an enabled group uses a supported positive raw id and resolves to a Telegram chat or channel entity
- **THEN** runtime derives the marked peer id from that entity before adding it to the addressed-reply allowlist

#### Scenario: Disabled group is ignored
- **WHEN** an incoming event chat id belongs to a configured but disabled group
- **THEN** the addressed reply router returns `false` and sends no response

#### Scenario: Non-reply message is ignored without sender lookup
- **WHEN** an incoming event is not a Telegram reply
- **THEN** the addressed reply router returns `false`, sends no response, and does not resolve the sender entity

#### Scenario: Reply to another bot is ignored
- **WHEN** the replied-to message sender id differs from the current bot Telegram user id
- **THEN** the addressed reply router returns `false` and sends no response

#### Scenario: Missing reply message is ignored
- **WHEN** an event is marked as reply but the replied-to message cannot be loaded
- **THEN** the addressed reply router returns `false`
