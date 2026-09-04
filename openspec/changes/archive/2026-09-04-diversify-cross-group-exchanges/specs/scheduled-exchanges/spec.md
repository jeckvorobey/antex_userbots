## MODIFIED Requirements

### Requirement: Bot and topic anti-repeat
The system SHALL combine persisted group-scoped anti-repeat with shared cross-group scheduling preferences. Avoiding an already used unordered pair in another group SHALL take priority over the local participant cooldown; among equally diverse pairs it SHALL preserve the strongest possible local cooldown. Topic freshness and question-text anti-repeat SHALL remain group-scoped, with other-group topic usage used to rank otherwise locally eligible topics.

#### Scenario: Recent bots are excluded when possible
- **WHEN** at least two candidates remain after excluding the last four scheduled bot ids for the group and this permits the lowest other-group pair-conflict score
- **THEN** the chosen initiator and responder come from remaining candidates

#### Scenario: Recent bot filter relaxes when pool is small
- **WHEN** excluding recent bots leaves fewer than two candidates
- **THEN** the orchestrator relaxes exclusion enough to choose a pair, subject to the cross-group ranking priorities

#### Scenario: Cross-group duplicate requires cooldown relaxation
- **WHEN** keeping the local cooldown would repeat a pair used by another group and an unused pair can be admitted by relaxing it
- **THEN** the orchestrator relaxes cooldown only as far as required to select a lowest-conflict pair

#### Scenario: Recent topic keys are avoided when alternatives exist
- **WHEN** topic selector has topics whose normalized signatures are absent from recent group topic keys
- **THEN** the orchestrator chooses from fresh topics, preferring the lowest recent other-group usage

#### Scenario: Repeated generated question is retried
- **WHEN** the AI client returns a question whose normalized signature is in recent group question signatures
- **THEN** the orchestrator asks the AI client again with an added anti-repeat instruction

### Requirement: Multi-group scheduled iteration
The system SHALL evaluate scheduling gates and maintain window records independently for every enabled group, while coordinating participant and topic choices through the shared persisted diversity summary.

#### Scenario: Same UTC window creates separate group exchanges
- **WHEN** two enabled groups are inside the same UTC window
- **THEN** the scheduler can create one exchange for each group using separate group-scoped window records
- **AND** each subsequent selection considers other groups' already saved plans

### Requirement: Important service scenario rotation
The system SHALL choose an initial important-service scenario randomly among configured scenarios with the lowest recent other-group usage/reservations when the group has no valid persisted scenario. After that initial choice it SHALL continue the persisted per-group cycle in the order `exchange_rub`, `booking_airbnb`, `exchange_usdt`, `booking_booking`. Existing groups SHALL continue their current cycle without resetting cadence or rewriting planned exchanges.

#### Scenario: Initial scenarios differ when alternatives exist
- **WHEN** three groups with no service history create initial exchanges with four configured scenarios
- **THEN** their initial scenario keys differ because each new selection accounts for the previously reserved keys

#### Scenario: Initial scenario pool exhausted
- **WHEN** a new group has no service history and every configured scenario has recent other-group usage
- **THEN** it chooses randomly among the least-used scenarios

#### Scenario: Previous scenario is no longer configured
- **WHEN** the group's latest persisted service key is absent from the configured scenario list
- **THEN** the orchestrator uses the same distributed initial-choice policy

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
