## ADDED Requirements

### Requirement: Exchange activity sort key
The system SHALL persist a `last_activity_at` timestamp on scheduled exchanges for recent and latest exchange lookups.

#### Scenario: New exchange stores activity timestamp
- **WHEN** `ExchangeStore.create_exchange` creates a planned exchange
- **THEN** the exchange has a non-empty `last_activity_at`

#### Scenario: Started exchange updates activity timestamp
- **WHEN** `ExchangeStore.mark_exchange_started` marks an exchange as started
- **THEN** `last_activity_at` equals the stored `started_at` value

#### Scenario: Completed exchange updates activity timestamp
- **WHEN** `ExchangeStore.mark_exchange_completed` marks an exchange as completed
- **THEN** `last_activity_at` equals the stored `completed_at` value

#### Scenario: Legacy exchange rows are backfilled
- **WHEN** `ExchangeStore.init_db` migrates a legacy `scheduled_exchanges` table with lifecycle timestamps but no `last_activity_at`
- **THEN** `last_activity_at` is filled from `completed_at`, `started_at`, or `created_at` in that priority order

### Requirement: Index-friendly exchange hot-path lookups
The system SHALL use persisted UTC timestamp strings and `last_activity_at` ordering for due, recent, and latest scheduled exchange queries.

#### Scenario: Due responder compares stored timestamps directly
- **WHEN** `get_due_started_exchange` checks due responder rows
- **THEN** it compares `responder_scheduled_at` to the serialized current UTC timestamp without wrapping the column in a SQL timestamp function

#### Scenario: Recent question context follows activity order
- **WHEN** recent scheduled questions are requested for a group
- **THEN** the returned rows are ordered by `last_activity_at` descending

#### Scenario: Latest important service exchange follows activity order
- **WHEN** latest important-service exchange state is requested for a group
- **THEN** the returned row is selected by `last_activity_at` descending

### Requirement: Activity indexes
The system SHALL create idempotent indexes that support group-scoped and chat-scoped recent exchange activity lookups.

#### Scenario: Activity indexes are created
- **WHEN** `ExchangeStore.init_db` runs
- **THEN** indexes for group/chat status and `last_activity_at` lookup exist without duplicate-index failure
