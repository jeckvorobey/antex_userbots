## 1. Tests

- [x] 1.1 Add runtime test proving unchanged group ticks reuse one orchestrator instance.
- [x] 1.2 Add runtime test or assertion proving cache is pruned/rebuilt when enabled groups change.

## 2. Implementation

- [x] 2.1 Add per-group orchestrator cache in `_run_swarm_mode`.
- [x] 2.2 Build stable group signatures and recreate orchestrators only when signatures change.
- [x] 2.3 Prune cache entries for disabled/removed groups after reload.

## 3. Verification

- [x] 3.1 Run runtime tests.
- [x] 3.2 Run `uv run pytest`.
- [x] 3.3 Run `openspec validate --all --strict`, sync specs, and archive the change.
