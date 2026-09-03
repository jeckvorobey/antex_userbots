## Why

Повторная временная ошибка при reconnect удаляет runtime-ссылку на клиента и превращает следующую попытку в `KeyError`, навсегда оставляя аккаунт offline. Одновременно scheduler хранит ссылку на стартовый Telegram-клиент и после его runtime-disable может срывать каждый tick при разрешении новых или изменённых групп.

## What Changes

- Сделать повторные reconnect-попытки независимыми от наличия предыдущего клиента в runtime-словаре.
- Для каждого scheduler tick выбирать актуальный активный Telegram-клиент, а при отсутствии активных клиентов безопасно пропускать tick.
- Добавить regression-тесты для обоих сценариев и обновить эксплуатационную документацию.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `swarm-runtime`: уточнить гарантии повторного reconnect и выбора активного клиента для разрешения групп scheduler-ом.

## Impact

Изменяются `userbot/swarm_manager.py`, `run.py`, связанные unit/integration tests, `openspec/specs/swarm-runtime/spec.md` и README. Публичные API, формат конфигурации и зависимости не меняются.
