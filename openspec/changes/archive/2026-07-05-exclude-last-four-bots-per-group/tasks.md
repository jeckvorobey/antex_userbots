# Tasks — exclude-last-four-bots-per-group

## Task 1: Обновить константу cooldown
- [x] В `userbot/orchestrator.py` изменить `RECENT_BOT_COOLDOWN_LIMIT = 3` на `RECENT_BOT_COOLDOWN_LIMIT = 4`.

## Task 2: Обновить тест anti-repeat
- [x] В `tests/test_orchestrator.py` в `test_orchestrator_avoids_recent_bots_and_last_topics` обновить мок `get_recent_bot_ids` чтобы возвращать 4 id, и добавить 6-го бота в пул.

## Task 3: Обновить тест деградации cooldown
- [x] В `tests/test_orchestrator.py` в `test_orchestrator_relaxes_recent_bot_filter_when_pool_is_too_small` обновить мок и пул ботов (4 бота в cooldown при пуле из 4).

## Task 4: Добавить тест group-scoped изоляции
- [x] В `tests/test_orchestrator.py` добавлен `test_orchestrator_passes_group_scope_to_recent_bot_ids`.

## Task 5: Запустить тесты
- [x] `uv run pytest tests/test_orchestrator.py tests/test_exchange_store.py` — 38 passed.
