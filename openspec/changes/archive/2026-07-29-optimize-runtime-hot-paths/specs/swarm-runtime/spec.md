## ADDED Requirements

### Requirement: Fair sequential group ticks
The system SHALL rotate the first processed group across scheduler ticks while keeping group execution sequential.

#### Scenario: Consecutive ticks rotate the starting group
- **WHEN** multiple enabled groups remain configured across consecutive scheduler ticks
- **THEN** each tick starts with the next group in cyclic configuration order

#### Scenario: Group execution remains sequential
- **WHEN** one scheduler tick processes multiple groups
- **THEN** the next group does not start `run_once` until the previous group finishes

#### Scenario: Reloaded groups reset safely
- **WHEN** settings reload changes the enabled group list
- **THEN** the next start index is normalized to the new list length without skipping or indexing outside the list
