## 1. Tests

- [x] 1.1 Add tests for shared connection configuration, lock retry, temporary initialization lock, and unknown OperationalError propagation
- [x] 1.2 Add concurrent tests for message writes, message plus exchange writes, and pruning plus writing
- [x] 1.3 Update existing persistence and runtime lifecycle fixtures for injected shared database ownership
- [x] 1.4 Add regression tests for retry exhaustion, read isolation, single runtime close, and partial initialization cleanup

## 2. Shared SQLite implementation

- [x] 2.1 Add `SQLiteDatabase` with one connection, PRAGMA configuration, one write lock, retry logging, rollback, and single close
- [x] 2.2 Refactor `MessageHistory` to use injected database reads and locked retry writes without owning a connection
- [x] 2.3 Refactor `ExchangeStore` to use injected database reads and locked retry writes without owning a connection
- [x] 2.4 Refactor runtime construction and shutdown to own exactly one shared SQLite database and clean up partial initialization

## 3. Documentation and validation

- [x] 3.1 Update project architecture documentation for shared SQLite ownership
- [x] 3.2 Run focused persistence/runtime tests and a stress test with at least 100 concurrent writes
- [x] 3.3 Run the full test suite and strict OpenSpec validation
- [ ] 3.4 Sync delta specs into main specs and archive the completed change
