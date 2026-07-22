## 1. Tests

- [x] 1.1 Add orchestrator coverage for rejecting a scheduled initiator question that matches the initiator bot's last 5 persisted questions in the same group.
- [x] 1.2 Add coverage for the non-match path so a fresh candidate is accepted and the existing group-level recent-question retry still works.

## 2. Orchestrator logic

- [x] 2.1 Load the initiator bot's recent session history with `chat_id`, `bot_id`, and a wider scan window before finalizing the scheduled question.
- [x] 2.2 Compare the normalized candidate question against the initiator bot's recent question signatures and reject the candidate when it collides.
- [x] 2.3 Select another random question from the remaining pool when a collision is detected, then fall back to the existing Gemini retry instruction if no safe candidate remains.

## 3. Verification and OpenSpec sync

- [x] 3.1 Run the targeted orchestrator and history tests for the new anti-repeat behavior.
- [x] 3.2 Sync the updated requirement into the main OpenSpec specs and archive the change after implementation is verified.
