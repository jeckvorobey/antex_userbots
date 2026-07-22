## Why

The scheduler tick currently creates a new `SwarmOrchestrator` for every enabled group on every tick. This is a small but avoidable allocation path that grows with group count and repeats stable dependency wiring.

## What Changes

- Cache one `SwarmOrchestrator` per enabled group while its effective runtime settings remain unchanged.
- Rebuild a cached orchestrator when group settings, resolved target/chat id, or skip-human-activity setting changes.
- Remove cached orchestrators for groups that disappear or become disabled after reload.

## Capabilities

### New Capabilities

### Modified Capabilities
- `swarm-runtime`: scheduler tick reuses group orchestrators when group runtime signature is unchanged.

## Impact

Affected area is `run.py` plus runtime tests. No public Telegram, DB, prompt, or config schema behavior changes are intended.
