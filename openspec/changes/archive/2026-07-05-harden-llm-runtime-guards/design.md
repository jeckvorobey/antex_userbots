## Context

The repository is not a web server, so the highest-value security fixes are runtime controls around abuse, data minimization, model-output publication, and local data retention. The current implementation already has useful building blocks: strict config validation, group scoping, bot scoping, persisted history, and centralized Gemini calls.

The design should avoid architectural churn. The safest approach is to add narrow guards around the existing reply and scheduled paths rather than trying to redesign prompt composition or the swarm runtime.

## Goals / Non-Goals

**Goals:**
- Block bursty abuse on the addressed human reply path before Gemini is called.
- Allow operators to disable external LLM usage for replies or scheduled exchanges without changing code.
- Reduce sensitive prompt leakage by redacting obvious secret-like and invite-link content before Gemini calls.
- Prevent unsafe model output from being sent directly to Telegram.
- Prune old plaintext history automatically using a configurable retention window.

**Non-Goals:**
- No change to the single `swarm` app mode.
- No full DLP system or cryptographic at-rest storage layer.
- No network-layer auth redesign for Telegram users.

## Decisions

- Add a dedicated runtime security section under `swarm.security`.
  - Rationale: these controls are runtime behavior guards, not Gemini model tuning knobs.
  - Alternative considered: place the fields under `[gemini]` or `[swarm.orchestrator]`. Rejected because it mixes unrelated concerns and makes future security settings harder to reason about.

- Use an in-memory sliding-window limiter for addressed replies keyed by `(chat_id, sender_id, bot_id)`.
  - Rationale: it is cheap, local to the existing process model, and blocks the highest-value abuse path before external cost is incurred.
  - Alternative considered: persist rate-limit state in SQLite. Rejected because it adds write amplification and complexity for a best-effort guard.

- Apply redaction close to the Gemini boundary and output validation close to the Telegram send boundary.
  - Rationale: boundary-local controls are easier to reason about and harder to bypass accidentally.
  - Alternative considered: embed all security rules directly in prompts. Rejected because prompt-only controls are weaker and unverifiable.

- Use safe fallback text when model output is blocked instead of dropping the whole flow silently.
  - Rationale: avoids strange runtime gaps and keeps user-facing behavior predictable.
  - Alternative considered: hard-fail the interaction. Rejected because it would degrade normal group behavior too sharply.

- Add retention cleanup methods for both message history and scheduled exchanges and run them during runtime bootstrap.
  - Rationale: startup cleanup is simple, deterministic, and good enough for this process model.
  - Alternative considered: a background scheduler job. Rejected because it adds moving parts without strong need.

## Risks / Trade-offs

- [Risk] Strict output filtering can occasionally block acceptable model text. -> Mitigation: keep the policy narrow and configurable and return a short safe fallback.
- [Risk] In-memory rate limiting resets on process restart. -> Mitigation: treat it as an abuse guard, not a strict accounting system.
- [Risk] Redaction may reduce answer quality in edge cases. -> Mitigation: redact only obvious secrets, invite links, and token-like strings.
- [Risk] Retention cleanup changes long-lived context availability. -> Mitigation: default to a conservative retention window and make it configurable.
