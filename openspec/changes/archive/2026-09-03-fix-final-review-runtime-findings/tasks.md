## 1. Regression Tests

- [x] 1.1 Add a test proving scheduled LLM gate changes invalidate the group orchestrator cache
- [x] 1.2 Add a test proving removal of all TOML groups does not restore the previous group on reload
- [x] 1.3 Add tests proving important-service disabled/unsafe generation uses a safe fallback with the approved URL
- [x] 1.4 Add a test proving permanent-send quarantine persistence failure still disables the bot before propagating

## 2. Runtime Fixes

- [x] 2.1 Include scheduled LLM permission in the effective orchestrator signature
- [x] 2.2 Preserve only original group fallback inputs across Settings reload
- [x] 2.3 Select an important-service-specific safe responder fallback
- [x] 2.4 Reorder permanent-send quarantine and disable operations while retaining persistence observability

## 3. Documentation and Verification

- [x] 3.1 Update README and synchronize the three modified OpenSpec capabilities
- [x] 3.2 Run targeted and full tests, dependency audit, diff checks, and strict OpenSpec validation
