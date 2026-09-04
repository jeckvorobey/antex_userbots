## 1. Addressed reply hot path

- [x] 1.1 Add tests for non-reply early rejection and DEBUG-only ignore logging
- [x] 1.2 Add tests for expired rate-limit key cleanup
- [x] 1.3 Add tests for per-bot pending capacity, release on failure/cancellation, and absolute reply deadline
- [x] 1.4 Implement router ordering, cleanup, pending capacity, and deadline behavior
- [x] 1.5 Add and document `addressed_reply_max_pending_per_bot` runtime configuration

## 2. Scheduler fairness

- [x] 2.1 Add runtime tests for sequential round-robin group ordering and reload normalization
- [x] 2.2 Implement persistent next-group index inside the scheduler closure

## 3. Prompt and persona cache

- [x] 3.1 Add tests for cache hit, file refresh, missing file, and event-loop-safe IO
- [x] 3.2 Implement reusable async text-file cache for prompt and persona loading

## 4. Indexed history range

- [x] 4.1 Add history tests for timestamp ordering and query-plan index range usage
- [x] 4.2 Replace SQLite datetime functions with direct canonical UTC comparison

## 5. Documentation and verification

- [x] 5.1 Sync affected main specs and update README/config documentation
- [x] 5.2 Run focused tests, full pytest, complexity scan, and strict OpenSpec validation
- [x] 5.3 Run security-best-practices review, fix confirmed findings, and repeat validation
- [ ] 5.4 Archive completed OpenSpec changes

## 6. Security review remediation

- [x] 6.1 Add regression tests for fail-closed empty allowlist and resolved target-only groups
- [x] 6.2 Implement resolved group id collection before handlers and during reload ticks
- [x] 6.3 Upgrade vulnerable locked runtime dependencies and repeat `pip-audit`
- [x] 6.4 Update the security report and run full validation
