## ADDED Requirements

### Requirement: Fail-closed Coolify volume identity validation
Before opening SQLite or Telegram connections in the Coolify production path, the process MUST verify that the effective database parent is the expected `/app/data` mount and that a pre-provisioned regular marker matches the non-empty `COOLIFY_RESOURCE_UUID`.

#### Scenario: Correct Coolify volume is mounted
- **WHEN** `/app/data` is present in the Linux mount table and its regular `.coolify-resource-uuid` marker matches `COOLIFY_RESOURCE_UUID`
- **THEN** startup logs successful non-secret volume validation and proceeds to the handover delay and runtime lock

#### Scenario: Production data directory is not a mount point
- **WHEN** the effective database resolves under `/app/data` but `/app/data` is absent from the Linux mount table
- **THEN** startup fails before creating a runtime lock, SQLite file, or Telegram connection

#### Scenario: Volume marker is missing or mismatched
- **WHEN** the production mount marker is absent, empty, a symbolic link, a non-regular file, or does not match `COOLIFY_RESOURCE_UUID`
- **THEN** startup fails without creating or replacing the marker and without opening SQLite or Telegram connections

#### Scenario: Local and in-memory execution
- **WHEN** the database is `:memory:` or its effective parent is outside `/app/data` without Coolify runtime indicators
- **THEN** Coolify volume validation is skipped so local tests and development remain supported

### Requirement: Bounded graceful cleanup
Every graceful-shutdown or partial-startup external-resource cleanup operation MUST have a finite deadline, MUST log timeout/error without secrets, and MUST allow cleanup of the remaining resources before the runtime lock is released.

#### Scenario: Registered Telegram client stop hangs
- **WHEN** one registered client does not complete `stop()` within the client cleanup timeout
- **THEN** the manager logs that bot timeout and still attempts to stop every remaining client

#### Scenario: Cancellation occurs during one client startup
- **WHEN** shutdown cancels a client during startup and that unregistered client does not stop within the client cleanup timeout
- **THEN** startup cleanup times out, manager cleanup continues for registered clients, and application shutdown proceeds

#### Scenario: SQLite resource close hangs
- **WHEN** one persistence resource does not close within its cleanup timeout
- **THEN** the timeout is logged, the other persistence resource is still closed, and the runtime lock is released after both cleanup attempts finish

#### Scenario: Cleanup completes within Coolify grace budget
- **WHEN** all cleanup operations reach either completion or their configured deadlines
- **THEN** the application finishes its internal shutdown budget with margin below the documented production Coolify stop grace period
