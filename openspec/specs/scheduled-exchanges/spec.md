# Scheduled Exchanges

## Purpose

Define orchestrated bot-to-bot exchanges started by the scheduler.
## Requirements
### Requirement: Exchange tick gating
The system SHALL skip starting new scheduled exchanges for a group when runtime gates disallow them.

#### Scenario: Outside active window is skipped
- **WHEN** the current UTC time is outside the group's effective `active_windows_utc`
- **THEN** `run_once` returns `false` without creating a new exchange for that group

#### Scenario: Recent human activity is skipped
- **WHEN** `skip_if_recent_human_activity` is enabled and the human activity checker reports activity
- **THEN** `run_once` returns `false`

#### Scenario: Missing group target is skipped
- **WHEN** no resolved group target or real group chat id is available to the orchestrator
- **THEN** `run_once` returns `false`

### Requirement: One exchange per active window
The system SHALL create at most one scheduled exchange record per group and computed window key.

#### Scenario: Existing completed exchange blocks new exchange in same group window
- **WHEN** `ExchangeStore` already has an exchange for the current group and window key with non-planned status
- **THEN** the orchestrator does not create another exchange for that group window

#### Scenario: Existing planned exchange can be resumed
- **WHEN** `ExchangeStore` already has a planned exchange for the current group and window key
- **THEN** the orchestrator attempts the due initiator stage for that existing exchange

### Requirement: Bot and topic anti-repeat
The system SHALL use persisted group-scoped exchange state to reduce repeated scheduled participants, topics, and question text.

#### Scenario: Recent bots are excluded when possible
- **WHEN** at least two candidates remain after excluding the last four scheduled bot ids for the group
- **THEN** the chosen initiator and responder come from remaining candidates

#### Scenario: Recent bot filter relaxes when pool is small
- **WHEN** excluding recent bots leaves fewer than two candidates
- **THEN** the orchestrator relaxes exclusion enough to choose a pair

#### Scenario: Recent topic keys are avoided when alternatives exist
- **WHEN** topic selector has topics whose normalized signatures are absent from recent group topic keys
- **THEN** the orchestrator chooses from fresh topics

#### Scenario: Repeated generated question is retried
- **WHEN** the AI client returns a question whose normalized signature is in recent group question signatures
- **THEN** the orchestrator asks the AI client again with an added anti-repeat instruction

### Requirement: Initiator stage
The system SHALL create a planned exchange and send the initiator message to the resolved group only when due.

#### Scenario: Planned exchange waits for due time
- **WHEN** `initiator_scheduled_at` is later than now
- **THEN** the message is not sent and `run_once` returns `false`

#### Scenario: Initiator sends city-adapted start topic
- **WHEN** a planned exchange is due and its scheduled slot is acquired
- **THEN** the orchestrator composes `start_topic` with group context, asks the AI client for a city-specific question, sends it, marks the exchange started, and persists the initiator message

#### Scenario: Busy initiator defers exchange
- **WHEN** the scheduled slot is not acquired
- **THEN** no message is sent and the exchange remains retryable

### Requirement: Responder stage
The system SHALL send the responder message to the same group only after the persisted responder due time.

#### Scenario: Due responder sends reply
- **WHEN** `ExchangeStore` returns a due started exchange for a group and the responder slot is acquired
- **THEN** the orchestrator composes `reply` with group context, generates a response using bot-specific session history for that group, sends it as a reply to the initiator message id in that group, saves a `scheduled_responder` message, and marks the exchange completed

#### Scenario: Busy responder defers response
- **WHEN** the responder scheduled slot is not acquired
- **THEN** the due response is not sent and the exchange remains started for retry

### Requirement: Second-precision scheduling
The system SHALL choose random initiator and responder times with second precision inside configured ranges.

#### Scenario: Initiator due time is within remaining window
- **WHEN** an active window has already started
- **THEN** the initiator due time is not earlier than the current time and remains before the window end when possible

#### Scenario: Responder delay uses seconds
- **WHEN** `responder_delay_minutes` is configured
- **THEN** the responder due timestamp is computed from a random second value inside that minute range

### Requirement: Multi-group scheduled iteration
The system SHALL evaluate scheduled exchanges independently for every enabled group.

#### Scenario: Same UTC window creates separate group exchanges
- **WHEN** two enabled groups are inside the same UTC window
- **THEN** the scheduler can create one exchange for each group using separate group-scoped window records

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

### Requirement: Initiator question anti-repeat uses bot history
The system SHALL compare each scheduled initiator question against the initiating bot's last 5 persisted questions in the same group before sending it.

#### Scenario: Matching recent bot question is rejected
- **WHEN** a scheduled initiator question matches one of the initiator bot's last 5 questions after normalization
- **THEN** the orchestrator rejects that candidate and selects another random question from the remaining pool instead of sending the repeat

#### Scenario: Non-matching bot question is accepted
- **WHEN** a scheduled initiator question does not match any of the initiator bot's last 5 questions after normalization
- **THEN** the orchestrator accepts the question and continues the scheduled exchange flow

#### Scenario: Limited history still works
- **WHEN** fewer than 5 persisted questions exist for the initiator bot in the current group
- **THEN** the orchestrator uses all available bot history entries for the anti-repeat check

### Requirement: Existing group question anti-repeat remains in effect
The system SHALL continue retrying a generated scheduled question when its normalized signature appears in recent group question signatures.

#### Scenario: Group recent signature still triggers retry
- **WHEN** the AI client returns a question whose signature is present in recent group signatures
- **THEN** the orchestrator retries generation with the existing anti-repeat instruction

### Requirement: Important service publication contract
The system SHALL publish an important-service initiator without the approved contact and a responder containing the exact approved contact.

#### Scenario: Initiator model leaks contact
- **WHEN** generated important-service question includes the approved contact
- **THEN** runtime replaces it with a safe non-promotional question

#### Scenario: Responder omits contact
- **WHEN** generated important-service answer is otherwise safe but lacks the approved contact
- **THEN** runtime replaces it with the approved contact fallback

### Requirement: Important service requires responder turn
The system SHALL schedule important-service exchanges only when the group allows at least two turns.

#### Scenario: One-turn group is due
- **WHEN** important-service cadence is due and `max_turns_per_exchange` is less than two
- **THEN** runtime selects a regular exchange rather than completing an unanswered service question

### Requirement: Cooldown includes only published participants
The system SHALL count a responder in recent-bot cooldown only when its Telegram message was persisted as sent.

#### Scenario: One-turn exchange completes
- **WHEN** an exchange completes after only the initiator publishes
- **THEN** the configured but unsent responder is absent from recent-bot results
