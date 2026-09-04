## Why

Persisted quarantine currently returns rows for accounts that are no longer present in the active TOML configuration. Those stale rows make startup logs misleading and can hide the distinction between current numeric Telegram IDs and retired personas.

## What Changes

- Scope durable quarantine lookup to the bot IDs currently configured for this runtime.
- Preserve exact string matching so numeric IDs of any length are handled without numeric conversion.
- Keep the existing behavior for callers that do not provide a configured-ID set.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `swarm-runtime`: startup durable quarantine filtering is scoped to configured bot profiles.

## Impact

The `ExchangeStore` lookup, swarm startup wiring, and their tests change. No database migration or external dependency is required.
