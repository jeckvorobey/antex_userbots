## 1. Exchange Store Hot Paths

- [x] 1.1 Add tests for `last_activity_at` legacy migration and backfill.
- [x] 1.2 Add tests for lifecycle updates to `last_activity_at`.
- [x] 1.3 Add tests that recent question ordering follows `last_activity_at`.
- [x] 1.4 Implement `last_activity_at` migration, writes, indexes, and query rewrites.

## 2. Topic Key Cache

- [x] 2.1 Add tests for cached `TopicSelector.topic_key`.
- [x] 2.2 Implement topic key caching in `TopicSelector`.
- [x] 2.3 Update `SwarmOrchestrator` to use cached topic keys with fallback.

## 3. Validation And Specs

- [x] 3.1 Run targeted exchange store, scheduler, and orchestrator tests.
- [x] 3.2 Run full test suite.
- [x] 3.3 Sync OpenSpec deltas into main specs.
- [x] 3.4 Archive the completed change.
