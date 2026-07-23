## 1. Tests

- [x] 1.1 Add a runtime test proving that multi-group membership waits 20 seconds only between consecutive enabled groups and keeps the existing initial delay.

## 2. Runtime implementation

- [x] 2.1 Add a fixed 20-second group join interval and apply it between sequential enabled-group membership operations in the multi-group startup hook.
- [x] 2.2 Preserve the existing single-group startup hook, disabled-group skipping, dialog-index reuse, and no-trailing-delay behavior.

## 3. Verification and documentation

- [x] 3.1 Run targeted runtime tests and the full test suite.
- [x] 3.2 Validate the OpenSpec change strictly and sync the completed delta into the main swarm-runtime specification.
- [x] 3.3 Archive the completed OpenSpec change after all checks pass.
