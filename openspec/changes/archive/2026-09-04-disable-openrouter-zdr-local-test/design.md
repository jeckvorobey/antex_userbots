## Context

The local configuration uses free models that are present in the OpenRouter catalog but have no endpoint matching `zdr=true`. The provider returns 404 before generation. A direct probe without ZDR reached the provider and returned rate limiting instead, confirming endpoint selection rather than invalid model slugs.

## Goals / Non-Goals

**Goals:**

- Send `zdr=false` so local scheduled generation can use ordinary available endpoints.
- Preserve all other request safety controls and avoid exposing raw provider responses.

**Non-Goals:**

- Changing model order or adding paid models.
- Removing prompt sanitization, fallback routing, or retry bounds.

## Decisions

- Set the existing provider `zdr` boolean to `false`; retain `data_collection="deny"` and the other provider preferences.
- Make the privacy trade-off explicit in documentation and final operator instructions.

## Risks / Trade-offs

- [Risk] The provider may retain request data according to its ordinary policy. → This setting is for local testing only; restore ZDR-compatible models/policy before production use.
- [Risk] Free endpoints may return 429. → Keep ordered fallbacks and bounded retry behavior.
