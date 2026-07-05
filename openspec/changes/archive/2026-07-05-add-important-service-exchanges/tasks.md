## 1. Persistence Tests And Store Changes

- [x] 1.1 Add failing tests in `tests/test_exchange_store.py` for idempotent migration of `exchange_kind` and `important_scenario`.
- [x] 1.2 Add failing tests for creating regular and important-service exchanges with correct metadata.
- [x] 1.3 Add failing tests for group-scoped latest important-service lookup and scenario retrieval.
- [x] 1.4 Implement `ExchangeStore` column migration, indexes, create-time metadata, and latest important-service query helpers.

## 2. Orchestrator Tests And Behavior

- [x] 2.1 Add failing tests in `tests/test_orchestrator.py` for per-group UTC calendar-day cadence where a July 5 important exchange is next eligible on July 8.
- [x] 2.2 Add failing tests for scenario rotation: `exchange_rub` -> `booking_airbnb` -> `exchange_usdt` -> `booking_booking` -> `exchange_rub`.
- [x] 2.3 Add failing tests that important-service exchanges reuse active-window, recent-human-activity, and one-exchange-per-window gates.
- [x] 2.4 Add failing tests that an eligible important-service exchange replaces ordinary topic selection for that group window.
- [x] 2.5 Implement important-service scenario definitions, cadence decision, rotation decision, exchange creation metadata, and specialized prompt context in `userbot/orchestrator.py`.

## 3. Prompt Contract Updates

- [x] 3.1 Add or update tests that verify important-service context includes `important_service_question`, `important_service_answer`, scenario intent, answer intent, and `@tt_exchenge_bot`.
- [x] 3.2 Update `ai/prompts/start_topic.md` so important-service questions stay conversational and never mention `@tt_exchenge_bot`.
- [x] 3.3 Update `ai/prompts/reply.md` so only `important_service_answer` contexts require a natural, varied mention of `@tt_exchenge_bot`.
- [x] 3.4 Verify ordinary scheduled exchange prompt behavior remains non-promotional without the important-service markers.

## 4. Integration, Documentation, And Validation

- [x] 4.1 Update project documentation to describe important-service exchanges, per-group cadence, scenario order, and prompt behavior.
- [x] 4.2 Run targeted tests for exchange store, orchestrator, prompt composition, and prompt/Gemini contracts.
- [x] 4.3 Run the full relevant test suite with `uv run pytest`.
- [x] 4.4 Sync OpenSpec deltas into main specs after implementation.
- [x] 4.5 Archive the completed OpenSpec change after tests pass.
