## 1. Tests

- [x] 1.1 Add runtime tests proving that multi-group startup scans dialogs once and reuses the index.
- [x] 1.2 Add runtime tests for index updates after join and independent per-group target caching.

## 2. Runtime implementation

- [x] 2.1 Implement reusable dialog indexing for membership checks without changing sequential bot startup.
- [x] 2.2 Replace the scalar resolved-target cache with a normalized per-group cache.

## 3. Verification

- [x] 3.1 Run targeted runtime tests and the full test suite.
- [x] 3.2 Run strict OpenSpec validation and verify the final diff.

## 4. Review remediation

- [x] 4.1 Add a regression test for colliding Telegram user and channel raw IDs.
- [x] 4.2 Preserve peer namespaces in the dialog index and repeat all validation gates.
