## MODIFIED Requirements

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
