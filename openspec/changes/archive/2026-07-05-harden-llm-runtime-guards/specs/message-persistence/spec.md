## ADDED Requirements

### Requirement: History retention cleanup
The system SHALL support deleting persisted message and scheduled exchange rows older than the configured retention window.

#### Scenario: Old history is pruned at runtime bootstrap
- **WHEN** runtime initializes persistence with a positive retention window
- **THEN** messages and scheduled exchanges older than the cutoff are deleted before normal operation continues

#### Scenario: Non-positive retention disables pruning
- **WHEN** the configured retention window is zero or negative
- **THEN** automatic history pruning is skipped
