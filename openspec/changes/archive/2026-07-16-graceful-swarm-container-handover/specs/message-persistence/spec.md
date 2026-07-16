## ADDED Requirements

### Requirement: SQLite bootstrap lock resilience
The system MUST tolerate bounded temporary SQLite locks during runtime bootstrap without masking unrelated database errors.

#### Scenario: Temporary database lock clears
- **WHEN** persistence initialization receives `database is locked` and the lock clears within the configured retry window
- **THEN** partial connections are closed and runtime bootstrap is retried until initialization succeeds

#### Scenario: Database remains locked
- **WHEN** all bounded bootstrap retries are exhausted by SQLite lock errors
- **THEN** startup fails with the final lock error and does not start Telegram clients

#### Scenario: Unrelated database error occurs
- **WHEN** persistence initialization raises an `OperationalError` that is not a lock error
- **THEN** startup fails immediately without lock-specific retry

### Requirement: SQLite connection busy timeout
Message history and exchange persistence connections MUST use the same explicit SQLite busy timeout.

#### Scenario: Short writer overlap occurs
- **WHEN** a SQLite write is briefly blocked by another connection within the busy timeout
- **THEN** the connection waits for the lock instead of failing immediately
