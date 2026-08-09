## Why

При выборе пары для scheduled exchange orchestrator повторно проходит весь roster для каждого уровня cooldown.

## What Changes

- Вычислять максимальный допустимый cooldown за один проход по roster и history prefix.
- Сохранить состав и порядок кандидатов, а также правило ослабления cooldown.

## Capabilities

### New Capabilities

- `efficient-bot-candidate-selection`: Линейный выбор кандидатов для scheduled exchange.

### Modified Capabilities

- Нет.

## Impact

- `userbot/orchestrator.py` и `tests/test_orchestrator.py`.
