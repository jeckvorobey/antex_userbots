## Why

The configured free OpenRouter models return HTTP 404 when the provider is forced to use zero-data-retention (ZDR) endpoints, so scheduled test generation cannot start.

## What Changes

- Disable the OpenRouter provider `zdr` preference for this local test runtime.
- Keep provider fallbacks, parameter requirements, input redaction, and safe error logging unchanged.
- Update request-contract tests and generation specifications.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `prompt-and-generation`: provider requests explicitly opt out of ZDR to use available test endpoints.

## Impact

Only the OpenRouter request payload, tests, and related specification change. This is a deliberate reduction of provider-side retention protection for local testing.
