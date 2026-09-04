## ADDED Requirements

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
