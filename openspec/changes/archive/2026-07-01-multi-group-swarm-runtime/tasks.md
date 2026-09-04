## 1. Specification And Tests

- [x] 1.1 Add OpenSpec delta specs for multi-group config, runtime, routing, scheduling, persistence, and prompts.
- [x] 1.2 Add failing tests for TOML groups, schedule inheritance, duplicate ids, invalid targets, and reload detection.
- [x] 1.3 Add failing tests for group-scoped ExchangeStore queries and idempotent migration.
- [x] 1.4 Add failing tests for router group filtering and orchestrator per-group behavior.

## 2. Core Implementation

- [x] 2.1 Implement group config/runtime models and remove `[target]` from strict TOML.
- [x] 2.2 Implement settings reload watcher and effective group schedule derivation.
- [x] 2.3 Add group columns and group filters to ExchangeStore.
- [x] 2.4 Make AddressedReplyRouter ignore unknown or disabled groups.
- [x] 2.5 Make SwarmOrchestrator group-aware for window keys, due exchanges, history chat ids, resolved targets, and prompt context.
- [x] 2.6 Update runtime startup/membership and scheduler loop to iterate enabled groups and refresh group state after reload.

## 3. Documentation And Verification

- [x] 3.1 Update settings examples, env example, README, project docs, and main OpenSpec specs.
- [x] 3.2 Run `uv run pytest`.
- [x] 3.3 Run `openspec validate --all --strict`, sync specs, and archive the completed change.
