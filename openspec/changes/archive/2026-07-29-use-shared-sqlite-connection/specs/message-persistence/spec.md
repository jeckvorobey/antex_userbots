## ADDED Requirements

### Requirement: Shared SQLite database
The system SHALL use one shared `aiosqlite.Connection` and one shared asynchronous write lock for message history and scheduled exchange persistence during a runtime.

#### Scenario: Persistence components share one connection
- **WHEN** runtime initializes message history and exchange storage
- **THEN** both components receive the same open SQLite database dependency and neither component opens or closes its own connection

#### Scenario: Concurrent writes are serialized
- **WHEN** message inserts, exchange inserts, updates, deletes, schema creation, migrations, or index creation run concurrently
- **THEN** each write operation and its commit execute under the same asynchronous lock

#### Scenario: Reads wait for active writes
- **WHEN** a read starts while another coroutine has an unfinished write transaction
- **THEN** the read waits for that transaction to commit or roll back before querying the shared connection

### Requirement: SQLite connection configuration
The system SHALL open the configured database path with a 30-second connection timeout and enable WAL journal mode, NORMAL synchronous mode, a 30000-millisecond busy timeout, and foreign key enforcement.

#### Scenario: Shared connection is configured
- **WHEN** the shared SQLite database opens
- **THEN** `journal_mode` is `wal`, `synchronous` is `NORMAL`, `busy_timeout` is `30000`, and `foreign_keys` is enabled

#### Scenario: Existing database files are preserved
- **WHEN** the shared SQLite database opens an existing `data/history.db`
- **THEN** it uses the existing database and does not delete the database, WAL, or shared-memory files

### Requirement: Temporary SQLite lock retry
The system SHALL execute a locked SQLite operation at most five times using delays of 0.2, 0.5, 1, and 2 seconds between attempts while preserving all non-lock errors.

#### Scenario: Temporary database lock is retried
- **WHEN** an operation raises `aiosqlite.OperationalError` containing `database is locked` or `database table is locked`
- **THEN** the system rolls back, logs the next attempt with its delay and operation name, waits, and retries within the five-attempt limit

#### Scenario: Schema initialization survives a temporary lock
- **WHEN** schema initialization encounters a temporary SQLite lock and a later attempt succeeds
- **THEN** initialization completes without terminating the runtime

#### Scenario: Unknown operational error is propagated
- **WHEN** an operation raises any other `aiosqlite.OperationalError`
- **THEN** the error is raised immediately without retry or suppression

#### Scenario: Retry limit is exhausted
- **WHEN** all five attempts fail with a recognized lock error
- **THEN** the final lock error is raised
