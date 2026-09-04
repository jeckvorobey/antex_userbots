## 1. Regression Tests

- [x] 1.1 Add failing tests that preserve durable quarantine and clean up partial startup clients
- [x] 1.2 Add failing tests for unresolved/write-restricted startup groups without global quarantine
- [x] 1.3 Add failing tests for membership and write validation of groups introduced by reload

## 2. Implementation

- [x] 2.1 Restrict startup snapshot deletion and implement partial-client cleanup
- [x] 2.2 Add group-specific availability errors and strict startup validation
- [x] 2.3 Validate new or changed groups for every active client before reload activation

## 3. Documentation And Delivery

- [x] 3.1 Update README and synchronize the swarm-runtime delta spec
- [x] 3.2 Run full tests, strict OpenSpec validation, dependency audit, and diff checks
- [x] 3.3 Archive the change, commit and push the fixes, rerun Codex Review and GitHub checks
