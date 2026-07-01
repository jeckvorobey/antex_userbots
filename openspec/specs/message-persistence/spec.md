# Message And Exchange Persistence

## Purpose

Define SQLite persistence for chat history and scheduled exchange state.

## Requirements

### Requirement: Message history table
The system SHALL create and migrate a `messages` table and supporting indexes for persisted chat history.

#### Scenario: History initialization creates storage
- **WHEN** `MessageHistory.init_db` runs against a file path
- **THEN** the parent directory is created as needed and the `messages` table exists

#### Scenario: History initialization is idempotent
- **WHEN** `MessageHistory.init_db` runs more than once
- **THEN** initialization succeeds without duplicate-column or duplicate-index failure

#### Scenario: History indexes are created
- **WHEN** `MessageHistory.init_db` runs
- **THEN** indexes exist for user history and chat/bot session history lookups

### Requirement: User history retrieval
The system SHALL persist messages by user id and return limited chronological history.

#### Scenario: User messages are isolated
- **WHEN** messages are saved for different user ids
- **THEN** `get_history(user_id)` returns only that user's messages

#### Scenario: History limit is applied
- **WHEN** more messages exist than the requested limit
- **THEN** only the limited number of most recent messages is returned in chronological order

### Requirement: Session history retrieval
The system SHALL retrieve chat-scoped session history with optional bot and session-start filters.

#### Scenario: Chat history includes multiple users
- **WHEN** multiple users have messages in the same chat
- **THEN** `get_session_history(chat_id)` returns messages from those users in chronological order

#### Scenario: Different chats are isolated
- **WHEN** messages exist in different chats
- **THEN** `get_session_history` returns only messages for the requested chat id

#### Scenario: None chat id returns empty list
- **WHEN** `get_session_history` is called with `chat_id = None`
- **THEN** it returns an empty list

#### Scenario: Session start filters old messages
- **WHEN** `session_start` is provided
- **THEN** only messages at or after that UTC-normalized timestamp are returned

#### Scenario: Bot id filters session history
- **WHEN** `bot_id` is provided
- **THEN** session history contains only messages saved for that bot id

### Requirement: Swarm metadata persistence
The system SHALL persist swarm metadata with messages.

#### Scenario: Metadata is returned with session history
- **WHEN** a message is saved with `bot_id`, `exchange_id`, `message_origin`, and `reply_to_message_id`
- **THEN** `get_session_history` returns those metadata fields with role and text

### Requirement: Exchange state table
The system SHALL create and migrate a `scheduled_exchanges` table and supporting indexes for group-scoped orchestrator state.

#### Scenario: Exchange store initialization creates storage
- **WHEN** `ExchangeStore.init_db` runs
- **THEN** the `scheduled_exchanges` table exists with fields for group id, group chat id, pair, window, topic, question, due timestamps, message ids, status, and lifecycle timestamps

#### Scenario: Exchange store initialization is idempotent
- **WHEN** `ExchangeStore.init_db` runs with existing columns and indexes
- **THEN** initialization succeeds without duplicate-column or duplicate-index failure

#### Scenario: Exchange indexes are created
- **WHEN** `ExchangeStore.init_db` runs
- **THEN** indexes exist for group window lookup, due responder lookup, and recent anti-repeat queries

### Requirement: Exchange lifecycle state
The system SHALL persist planned, started, and completed scheduled exchange state by group.

#### Scenario: Planned exchange is created
- **WHEN** an exchange is created
- **THEN** it receives a UUID, group id, real group chat id, pair key, topic key, optional window key, optional initiator due timestamp, and status `planned`

#### Scenario: Exchange is marked started
- **WHEN** the initiator message is sent
- **THEN** the exchange stores status `started`, initiator message id, question text, normalized question signature, responder due timestamp, and started timestamp

#### Scenario: Exchange is marked completed
- **WHEN** the responder stage completes or an exchange with one max turn is finished
- **THEN** the exchange status becomes `completed` and completed timestamp is stored

### Requirement: Exchange anti-repeat queries
The system SHALL expose group-scoped persisted queries used by orchestrator anti-repeat behavior while bounding transferred rows by caller limits where possible.

#### Scenario: Recent bot ids follow scheduled message order
- **WHEN** completed and started exchanges exist for multiple groups
- **THEN** recent bot id retrieval for a group returns unique bot ids only from that group in recent scheduled message order

#### Scenario: Recent bot ids are limited in SQL
- **WHEN** more unique scheduled bot ids exist than the requested limit
- **THEN** `get_recent_bot_ids(limit)` returns only the requested count without relying on Python to scan every event row

#### Scenario: Recent topic keys are limited
- **WHEN** more topic keys exist than the requested limit across multiple groups
- **THEN** only keys from the latest started or completed exchanges in the requested group up to the limit are returned

#### Scenario: Recent question signatures are normalized
- **WHEN** question signatures are stored with punctuation or spacing
- **THEN** anti-repeat queries use normalized lowercase signatures without punctuation for the requested group

#### Scenario: Due started exchange is returned
- **WHEN** a started exchange in a group has a responder due timestamp not later than now
- **THEN** `get_due_started_exchange` returns that group exchange record

### Requirement: Scheduled history chat id
The system SHALL save scheduled messages under the real resolved Telegram group chat id.

#### Scenario: Scheduled message uses resolved chat id
- **WHEN** an orchestrator sends scheduled initiator or responder text
- **THEN** message history stores `chat_id` equal to the resolved Telegram group id, not a global fallback
