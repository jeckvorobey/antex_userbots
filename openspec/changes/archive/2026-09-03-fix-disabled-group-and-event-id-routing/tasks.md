## 1. Regression Tests

- [x] 1.1 Add a test proving that an explicit all-disabled group list does not activate legacy fallback
- [x] 1.2 Add a test proving that positive raw group IDs use the resolved entity's marked Telethon peer ID

## 2. Runtime Fixes

- [x] 2.1 Restrict legacy group fallback to settings without an explicit group list
- [x] 2.2 Normalize addressed-reply allowlist IDs from the resolved Telegram entity before fallback

## 3. Documentation and Verification

- [x] 3.1 Sync the updated OpenSpec requirements and keep runtime documentation current
- [x] 3.2 Run targeted tests, the full test suite, security audit, diff checks, and strict OpenSpec validation
