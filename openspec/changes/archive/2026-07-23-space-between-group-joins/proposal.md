## Why

При startup один userbot последовательно проверяет membership во всех enabled-группах и может выполнить несколько join-запросов подряд. Нужен интервал 20 секунд между такими вступлениями, чтобы снизить частоту последовательных действий аккаунта в Telegram.

## What Changes

- Сохранить текущую случайную задержку 30–60 секунд перед первым membership check.
- Добавить фиксированную задержку 20 секунд между последовательными membership-проверками enabled-групп в multi-group startup hook.
- Не ждать дополнительные 20 секунд после последней группы и не задерживать single-group startup hook.
- Добавить regression-тест, проверяющий порядок и длительность задержек.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `swarm-runtime`: startup membership flow должен выдерживать 20-секундный интервал между последовательными вступлениями в группы.

## Impact

- `run.py`: multi-group startup membership hook и константа интервала.
- `tests/test_runtime.py`: async-тест задержки между membership operations.
- `openspec/specs/swarm-runtime/spec.md`: уточнение контракта startup membership.
- Внешние API, база данных, конфигурация и порядок запуска userbot не меняются.
