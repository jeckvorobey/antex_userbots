## Context

The orchestrator already avoids some repetition by retrying when Gemini returns a generated question whose normalized signature appears in recent group question signatures. That protects against short-term duplicate phrasing, but it does not account for a specific bot reusing one of its own recent questions across scheduled initiator turns.

The existing `MessageHistory` API already supports group-scoped session history with a `bot_id` filter and a caller-provided `limit`, so the change can stay local to orchestrator logic without adding new persistence tables or new public configuration. The implementation can scan a wider recent-history window and then keep the last five scheduled-initiator questions for the final anti-repeat check.

## Goals / Non-Goals

**Goals:**
- Prevent an initiator bot from sending a scheduled question that matches one of its last 5 persisted questions in the same group.
- Preserve the existing group-scoped scheduled-exchange anti-repeat behavior.
- Prefer another candidate from the remaining topic/question pool before falling back to a repeated generation retry.

**Non-Goals:**
- No new storage schema or migration.
- No changes to addressed replies or ordinary message history semantics.
- No new user-facing config knobs.

## Decisions

- Use `MessageHistory.get_session_history(chat_id=..., bot_id=..., limit=5)` as the source of the initiator bot's recent questions.
  - Rationale: the data already exists, the API already scopes by bot and chat, and the limit is small enough to keep the extra read cheap.
  - Alternative considered: add a dedicated "recent questions" query to storage. Rejected because it duplicates existing session-history capability and would expand the persistence surface unnecessarily.

- Treat the bot-specific anti-repeat check as an additional gate, not a replacement for the existing group-level question-signature retry.
  - Rationale: the current group-wide retry still protects against repeated phrasing from any scheduled exchange, while the new gate covers the bot's own recent question history.
  - Alternative considered: fold bot-specific filtering into the existing group-wide query. Rejected because the semantics are different and the current group-wide query should stay reusable for other exchanges.

- When a candidate question collides with the initiator's recent 5 questions, pick a different candidate from the remaining pool when possible, then retry Gemini only if the pool is exhausted or still collides.
  - Rationale: this matches the requested behavior more closely than simply rewording the same topic forever.
  - Alternative considered: only re-prompt Gemini on the same topic. Rejected because it can loop on the same semantic question and does not satisfy the "choose another random question from the remaining questions" intent as directly.

- Keep normalization consistent with existing anti-repeat logic.
  - Rationale: punctuation and spacing should not bypass the repeat guard.
  - Alternative considered: exact string comparison. Rejected because it would miss obvious duplicates with minor formatting changes.

## Risks / Trade-offs

- [Risk] The remaining topic pool can become small in tightly constrained deployments. → Mitigation: retain the existing retry path and only relax to Gemini regeneration when the filtered pool cannot produce a safe candidate.
- [Risk] Filtering by recent history may skip legitimately varied rephrasings that happen to normalize the same way. → Mitigation: this is an intentional conservative trade-off for visible repetition avoidance.
- [Risk] The extra history read adds one more database query on the initiator path. → Mitigation: the query is limited to 5 rows and stays within the existing SQLite connection.
