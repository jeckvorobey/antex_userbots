## MODIFIED Requirements

### Requirement: Initiator stage
The system SHALL create a planned exchange and send the initiator message to the resolved group only when its due time has arrived.

#### Scenario: Planned exchange waits for due time
- **WHEN** a planned exchange has `initiator_scheduled_at` later than now
- **THEN** the initiator message is not sent and `run_once` returns `false`

#### Scenario: Initiator sends city-adapted start topic
- **WHEN** the planned exchange is due and the initiator scheduled slot is acquired
- **THEN** the orchestrator composes `start_topic` with group context, asks Gemini to adapt the shared topic intent into a city-specific question, sends it to the resolved group target, marks the exchange started, and saves a `scheduled_initiator` message with the real group chat id

#### Scenario: Busy initiator defers exchange
- **WHEN** the initiator scheduled slot is not acquired
- **THEN** the exchange remains available for retry and no initiator message is sent
