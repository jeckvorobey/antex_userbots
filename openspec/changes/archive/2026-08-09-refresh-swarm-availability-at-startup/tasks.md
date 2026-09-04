## 1. Persisted availability snapshot

- [x] 1.1 Add reset and availability-record APIs with an idempotent SQLite migration.
- [x] 1.2 Add focused exchange-store tests for reset and both availability outcomes.

## 2. Startup eligibility

- [x] 2.1 Make the membership hook reject unknown or false write permission for any enabled group.
- [x] 2.2 Rebuild availability at startup and persist a result for every enabled profile.
- [x] 2.3 Run enabled startup checks with bounded asyncio concurrency.
- [x] 2.4 Add focused runtime and swarm-manager tests for recovery, frozen accounts, and group write denial.

## 3. Documentation and verification

- [x] 3.1 Update runtime documentation for the fresh startup snapshot.
- [x] 3.2 Run focused and full tests, then validate OpenSpec strictly.
