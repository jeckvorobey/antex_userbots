## Why

Each deployment currently delays every userbot's membership check by a random one to three minutes. This prolongs production readiness unnecessarily while the staggered startup guard is still required.

## What Changes

- Reduce the hardcoded random startup delay before each userbot membership check to an inclusive 30–60 second range.
- Keep the existing sequential bot startup, membership workflow, reconnect backoff, scheduled-exchange timing, and addressed-reply delay unchanged.
- Add deterministic regression coverage for the new range and the wait before membership handling.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `swarm-runtime`: Shorten and define the random per-bot membership-check startup delay.

## Impact

- `run.py` startup-hook timing only.
- Runtime tests and the `swarm-runtime` OpenSpec contract.
- No new configuration key, API, persistence change, prompt update, or deployment configuration change.
