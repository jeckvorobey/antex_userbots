## Context

OpenRouter generation is shared by addressed replies and scheduled exchanges. The adapter already redacts several obvious secrets, validates output after generation, uses bounded retries, and requests ZDR providers. Security review identified gaps at the provider request boundary, Telegram publication boundary, configuration boundary, and dependency lock.

## Goals / Non-Goals

**Goals:**

- Bound completion cost before generation while preserving the existing 400-character publish limit.
- Prevent model-authored arbitrary links while preserving the required Mini App contact.
- Redact credentials embedded in URLs before prompts leave the process.
- Mask OpenRouter key and proxy values throughout settings handling and unwrap them only at client construction.
- Remove the known `cryptography 49.0.0` advisory from the resolved environment.

**Non-Goals:**

- General-purpose content moderation or complete PII detection.
- Changing Telegram routing, message persistence, scheduling, database schema, or provider selection.
- Configuring remote OpenRouter account guardrails.

## Decisions

1. Every OpenRouter request will include `max_completion_tokens=256`. A fixed code constant matches the approved policy, avoids a new operator setting, and works together with the stricter post-generation character gate. Provider defaults were rejected because they do not bound application cost.
2. Output validation will parse URL-shaped `http`/`https` substrings and accept only the normalized exact Mini App URL. A narrow allowlist is preferred to hostname-only filtering because the published destination is already part of the product contract. Both plain and Markdown links pass through the same matcher.
3. Input redaction will replace complete URLs containing `userinfo` credentials while keeping existing invite/token rules. Broad email and phone redaction is excluded because it would alter legitimate group conversation without a defined PII policy.
4. `OPENROUTER_API_KEY` and optional `PROXY` will use Pydantic `SecretStr` in `Secrets` and `Settings`. Runtime wiring will call `get_secret_value()` only when constructing OpenRouter and Telethon clients. This preserves SDK interfaces while preventing accidental settings representation leaks.
5. The direct dependency floor and lock will move to `cryptography>=50.0.0`. No PKCS#7 call path exists in the application, but shipping the patched version removes latent exposure.

## Risks / Trade-offs

- [Legitimate new links are rejected] → Keep one explicit allowlist constant and require a reviewed policy update plus tests for future destinations.
- [256 tokens can truncate a provider response] → Existing prompts require short Telegram text and the 400-character gate remains authoritative.
- [SecretStr changes internal test/runtime types] → Unwrap only at client constructors and add facade/reload tests that assert masking and stable effective values.
- [Dependency major upgrade has compatibility changes] → Regenerate with `uv`, run the full suite, and repeat `pip-audit`.

## Migration Plan

1. Apply tests and runtime changes together.
2. Regenerate `uv.lock` for `cryptography>=50.0.0`.
3. Run targeted tests, full pytest, OpenSpec validation, and dependency audit.
4. Roll back by reverting this change set; no persisted data migration is required.

## Open Questions

None.
