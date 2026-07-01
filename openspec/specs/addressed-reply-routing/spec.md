# Addressed Reply Routing

## Purpose

Define how human replies in the target group are routed to exactly the bot being replied to.

## Requirements

### Requirement: Ignore non-addressed messages
The system SHALL ignore incoming events that are outside enabled configured groups or are not addressed replies to the current bot.

#### Scenario: Unknown group is ignored
- **WHEN** an incoming event chat id is not one of the enabled configured groups
- **THEN** the addressed reply router returns `false` and sends no response

#### Scenario: Disabled group is ignored
- **WHEN** an incoming event chat id belongs to a configured but disabled group
- **THEN** the addressed reply router returns `false` and sends no response

#### Scenario: Non-reply message is ignored
- **WHEN** an incoming event is not a Telegram reply
- **THEN** the addressed reply router returns `false` and sends no response

#### Scenario: Reply to another bot is ignored
- **WHEN** the replied-to message sender id differs from the current bot Telegram user id
- **THEN** the addressed reply router returns `false` and sends no response

#### Scenario: Missing reply message is ignored
- **WHEN** an event is marked as reply but the replied-to message cannot be loaded
- **THEN** the addressed reply router returns `false`

### Requirement: Ignore bot-originated input
The system SHALL ignore messages from known swarm user ids and Telegram bot senders.

#### Scenario: Swarm sender is ignored
- **WHEN** the incoming sender id is in `swarm_user_ids`
- **THEN** the addressed reply router returns `false`

#### Scenario: Telegram bot sender is ignored
- **WHEN** the incoming sender resolves to a Telegram bot account
- **THEN** the addressed reply router returns `false`

### Requirement: Answer addressed human reply
The system SHALL answer a human reply only when the reply targets the current bot inside an enabled configured group.

#### Scenario: Addressed reply is processed
- **WHEN** a non-bot human sender replies in an enabled configured group to a message sent by the current bot
- **THEN** the router loads session history for the chat and bot, composes the `reply` prompt with that bot persona, asks Gemini for a response, replies in Telegram, and returns `true`

### Requirement: Persist addressed reply history
The system SHALL persist both sides of an addressed human reply interaction under the event chat id.

#### Scenario: User and assistant messages are saved
- **WHEN** an addressed reply is processed successfully
- **THEN** the human message and generated assistant response are saved with `message_origin = "human_reply"`, the current `bot_id`, chat id, and reply target metadata

### Requirement: Human slot coordination
The system SHALL process addressed human replies inside the swarm manager human slot when a manager is available.

#### Scenario: Manager slot wraps processing
- **WHEN** the router is constructed with a manager
- **THEN** addressed reply processing occurs inside `manager.human_slot(bot_id)`
