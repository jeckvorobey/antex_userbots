## ADDED Requirements

### Requirement: Important service exchange metadata
The system SHALL persist whether a scheduled exchange is ordinary or important-service and SHALL persist the important-service scenario key for important-service exchanges.

#### Scenario: Important service exchange is created
- **WHEN** the orchestrator creates an important-service exchange
- **THEN** `scheduled_exchanges` stores `exchange_kind = important_service` and the selected `important_scenario`

#### Scenario: Ordinary exchange is created
- **WHEN** the orchestrator creates an ordinary scheduled exchange
- **THEN** `scheduled_exchanges` stores or treats the exchange as `exchange_kind = regular` with no important-service scenario

#### Scenario: Legacy rows remain regular
- **WHEN** `ExchangeStore.init_db` migrates an existing database whose `scheduled_exchanges` rows do not have important-service metadata
- **THEN** those rows are treated as ordinary scheduled exchanges

### Requirement: Important service state queries
The system SHALL expose group-scoped persisted queries for important-service cadence and scenario rotation.

#### Scenario: Latest important service exchange is returned by group
- **WHEN** important-service exchanges exist for multiple groups
- **THEN** querying the latest important-service exchange for `danang` returns only `danang` state

#### Scenario: Recent important service date is available
- **WHEN** a group has a started or completed important-service exchange
- **THEN** the store can return the latest important-service timestamp used for UTC calendar-day cadence checks

#### Scenario: Latest scenario drives rotation
- **WHEN** a group has a latest important-service exchange with scenario `booking_airbnb`
- **THEN** the store can return `booking_airbnb` so the orchestrator can select `exchange_usdt`

### Requirement: Important service indexes
The system SHALL create idempotent indexes that support group-scoped latest important-service exchange lookup.

#### Scenario: Important service indexes are created
- **WHEN** `ExchangeStore.init_db` runs
- **THEN** indexes for group, chat, exchange kind, important scenario, and recent lifecycle timestamp lookup exist without duplicate-index failure
