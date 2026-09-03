## MODIFIED Requirements

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

### Requirement: Existing group question anti-repeat remains in effect
The system SHALL continue retrying a generated scheduled question when its normalized signature appears in recent group question signatures.

#### Scenario: Group recent signature still triggers retry
- **WHEN** the AI client returns a question whose signature is present in recent group signatures
- **THEN** the orchestrator retries generation with the existing anti-repeat instruction
