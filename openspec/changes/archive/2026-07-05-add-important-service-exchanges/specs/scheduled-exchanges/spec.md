## ADDED Requirements

### Requirement: Important service exchange cadence
The system SHALL evaluate important-service exchange eligibility independently for every enabled group and SHALL schedule an important-service exchange only when the group has no important-service exchange on the current UTC date or the previous two UTC calendar dates.

#### Scenario: Group becomes eligible after two full quiet days
- **WHEN** a group completed an important-service exchange on 2026-07-05 UTC and the current date is 2026-07-08 UTC inside an active window
- **THEN** the orchestrator treats the group as eligible for the next important-service exchange

#### Scenario: Group is not eligible on the second calendar day
- **WHEN** a group completed an important-service exchange on 2026-07-05 UTC and the current date is 2026-07-07 UTC inside an active window
- **THEN** the orchestrator does not create a new important-service exchange for that group

#### Scenario: Cadence is scoped per group
- **WHEN** group `danang` completed an important-service exchange recently and group `batumi` has no recent important-service exchange
- **THEN** only `batumi` can be eligible for an important-service exchange

### Requirement: Important service scenario rotation
The system SHALL choose important-service scenarios from a persisted per-group cycle in the order `exchange_rub`, `booking_airbnb`, `exchange_usdt`, `booking_booking`.

#### Scenario: Initial scenario is exchange rub
- **WHEN** a group has no persisted important-service scenario history
- **THEN** the next important-service scenario is `exchange_rub`

#### Scenario: Airbnb follows exchange rub
- **WHEN** the latest important-service scenario for a group is `exchange_rub`
- **THEN** the next important-service scenario is `booking_airbnb`

#### Scenario: Exchange usdt follows Airbnb
- **WHEN** the latest important-service scenario for a group is `booking_airbnb`
- **THEN** the next important-service scenario is `exchange_usdt`

#### Scenario: Booking follows exchange usdt
- **WHEN** the latest important-service scenario for a group is `exchange_usdt`
- **THEN** the next important-service scenario is `booking_booking`

#### Scenario: Cycle repeats after Booking
- **WHEN** the latest important-service scenario for a group is `booking_booking`
- **THEN** the next important-service scenario is `exchange_rub`

### Requirement: Important service exchange uses normal scheduling gates
The system SHALL run important-service exchanges through the same active-window, recent-human-activity, group-target, one-exchange-per-window, scheduled-slot, and responder-delay gates used by ordinary scheduled exchanges.

#### Scenario: Important service waits for active window
- **WHEN** a group is due for an important-service exchange but the current UTC time is outside the group's effective `active_windows_utc`
- **THEN** the orchestrator does not create an important-service exchange

#### Scenario: Important service replaces ordinary topic in the current window
- **WHEN** a group is eligible for an important-service exchange and no exchange exists for the current group window key
- **THEN** the orchestrator creates one planned important-service exchange instead of choosing an ordinary topic for that window

#### Scenario: Existing window exchange blocks important service
- **WHEN** a group is eligible for an important-service exchange but the current group window already has a planned, started, or completed exchange
- **THEN** the orchestrator does not create an additional important-service exchange for that window

#### Scenario: Important service is skipped for recent human activity
- **WHEN** `skip_if_recent_human_activity` is enabled and the human activity checker reports activity
- **THEN** the orchestrator does not create an important-service exchange
