## ADDED Requirements

### Requirement: Exclusive swarm runtime ownership
The process MUST acquire an exclusive inter-process runtime lock derived from the effective SQLite path before it opens SQLite connections or starts Telegram clients.

#### Scenario: New container overlaps an active container
- **WHEN** a new container starts while another swarm process holds the runtime lock on the shared persistent volume
- **THEN** the new process waits without opening SQLite or Telegram connections until the old process releases the lock

#### Scenario: Runtime lock is acquired
- **WHEN** no active process holds the runtime lock after the startup handover delay
- **THEN** the process acquires the lock, logs the non-secret lock path, and continues runtime initialization

#### Scenario: Runtime lock path is replaced by a symbolic link
- **WHEN** the runtime lock path resolves to a symbolic link or another non-regular file
- **THEN** startup rejects that path without following it or changing the linked file

#### Scenario: Runtime lock file permissions are normalized
- **WHEN** the process opens an existing regular runtime lock file
- **THEN** it restricts the file mode to owner read and write permissions before acquiring the kernel lock

#### Scenario: Runtime lock wait expires
- **WHEN** another process keeps the runtime lock beyond the bounded startup timeout
- **THEN** startup fails with a clear error before SQLite or Telegram initialization

#### Scenario: In-memory tests do not require a file lock
- **WHEN** the effective SQLite path is `:memory:`
- **THEN** runtime ownership behaves as a no-op and does not create a lock file

### Requirement: Signal-driven graceful shutdown
The process MUST treat `SIGTERM` and `SIGINT` as graceful shutdown requests throughout startup and normal operation.

#### Scenario: Signal during normal supervision
- **WHEN** the process receives a shutdown signal while bot supervision is active
- **THEN** it stops scheduler work, cancels and awaits supervision tasks, disconnects all Telegram clients, closes both SQLite connections, and releases the runtime lock last

#### Scenario: Signal during bot startup
- **WHEN** the process receives a shutdown signal while a Telegram client is in a startup hook
- **THEN** the partially started client is disconnected and the remaining runtime resources are closed before the process exits

#### Scenario: Signal while waiting for ownership
- **WHEN** the process receives a shutdown signal during the handover delay or runtime lock wait
- **THEN** the wait stops promptly and the process exits without opening SQLite or Telegram connections

### Requirement: Complete client cleanup
The swarm manager MUST attempt to stop every created Telegram client during shutdown, including clients that fail or are cancelled before active-pool registration.

#### Scenario: Startup hook fails after client connection
- **WHEN** a client connects but its startup hook fails or is cancelled
- **THEN** that client is disconnected before the error or cancellation propagates

#### Scenario: One client stop fails
- **WHEN** stopping one client raises an error during shutdown
- **THEN** the manager logs the failure and still attempts to stop all remaining clients
