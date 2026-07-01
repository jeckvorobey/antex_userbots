## MODIFIED Requirements

### Requirement: Exchange state table
The system SHALL create and migrate a `scheduled_exchanges` table for group-scoped orchestrator state.

#### Scenario: Exchange store initialization creates storage
- **WHEN** `ExchangeStore.init_db` runs
- **THEN** the `scheduled_exchanges` table exists with fields for group id, group chat id, pair, window, topic, question, due timestamps, message ids, status, and lifecycle timestamps

#### Scenario: Exchange store initialization is idempotent
- **WHEN** `ExchangeStore.init_db` runs with existing columns
- **THEN** initialization succeeds without duplicate-column failure

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
The system SHALL expose group-scoped persisted queries used by orchestrator anti-repeat behavior.

#### Scenario: Recent bot ids follow scheduled message order
- **WHEN** completed and started exchanges exist for multiple groups
- **THEN** recent bot id retrieval for a group returns unique bot ids only from that group in recent scheduled message order

#### Scenario: Recent topic keys are limited
- **WHEN** more topic keys exist than the requested limit across multiple groups
- **THEN** only keys from the latest started or completed exchanges in the requested group up to the limit are returned

#### Scenario: Recent question signatures are normalized
- **WHEN** question signatures are stored with punctuation or spacing
- **THEN** anti-repeat queries use normalized lowercase signatures without punctuation for the requested group

#### Scenario: Due started exchange is returned
- **WHEN** a started exchange in a group has a responder due timestamp not later than now
- **THEN** `get_due_started_exchange` returns that group exchange record

## ADDED Requirements

### Requirement: Scheduled history chat id
The system SHALL save scheduled messages under the real resolved Telegram group chat id.

#### Scenario: Scheduled message uses resolved chat id
- **WHEN** an orchestrator sends scheduled initiator or responder text
- **THEN** message history stores `chat_id` equal to the resolved Telegram group id, not a global fallback
