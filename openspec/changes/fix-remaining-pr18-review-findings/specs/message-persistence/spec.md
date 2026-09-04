## ADDED Requirements

### Requirement: Scheduled group scope uses marked peer id
The system SHALL persist target-only scheduled exchanges and history under the same marked Telegram peer id emitted by incoming events.

#### Scenario: Target-only channel resolves
- **WHEN** a channel configured only by public target resolves to a positive raw entity id
- **THEN** scheduled persistence uses its negative `-100...` peer id

### Requirement: Skipped exchange transition exists
The concrete exchange store SHALL persist a terminal skipped state when no eligible replacement participant exists.

#### Scenario: Exchange cannot be reassigned
- **WHEN** runtime marks an exchange skipped with a safe reason
- **THEN** the row becomes terminal and is not retried as pending

### Requirement: Legacy exchange rows receive current group scope
The system SHALL assign pre-group-schema exchanges to the deterministic legacy group before group-scoped runtime queries begin.

#### Scenario: Existing started exchange has null group fields
- **WHEN** a single-group installation upgrades and resolves its current group
- **THEN** legacy rows receive that group id and chat id so the started responder turn remains resumable
