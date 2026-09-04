## 1. Specification And Tests

- [x] 1.1 Update tests that assert important-service prompt/context contact behavior to expect `https://t.me/tt_exchenge_bot/antex`.
- [x] 1.2 Add or update safety coverage proving the public miniapp URL remains publishable while private invite links stay blocked.

## 2. Implementation

- [x] 2.1 Replace the orchestrator important-service contact constant and style example with the miniapp URL.
- [x] 2.2 Update `ai/prompts/reply.md` to require natural miniapp URL mentions for `important_service_answer`.

## 3. Documentation And Verification

- [x] 3.1 Update README and main OpenSpec specs to describe the miniapp URL behavior.
- [x] 3.2 Run relevant pytest targets and OpenSpec validation, then archive the completed change.
