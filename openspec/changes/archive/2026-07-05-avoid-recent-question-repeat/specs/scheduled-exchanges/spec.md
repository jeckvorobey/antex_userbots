## ADDED Requirements

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
The system SHALL continue retrying a generated scheduled question when its normalized signature appears in the group's recent question signatures.

#### Scenario: Group recent signature still triggers retry
- **WHEN** Gemini returns a question whose normalized signature is present in the group's recent question signatures
- **THEN** the orchestrator retries generation with the existing anti-repeat instruction before accepting the question

