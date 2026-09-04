## Why

Codex Review выявил, что startup/reload может допустить бота без доступа ко всем enabled-группам, потерять durable quarantine или оставить частично запущенный Telegram-клиент. Это нарушает действующие гарантии доступности и ручного снятия quarantine.

## What Changes

- Сохранять durable quarantine при обновлении transient startup snapshot.
- Отличать group-level недоступность от глобальной блокировки аккаунта.
- Не допускать в active pool бот без resolved target и подтверждённого права записи во всех enabled-группах.
- Проверять membership и write permission для добавленных/изменённых групп после reload до их активации.
- Останавливать и удалять клиент после любого частичного startup failure.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `swarm-runtime`: уточнить durable quarantine, строгий startup membership, reload новых групп и cleanup клиента.

## Impact

- `userbot/exchange_store.py`, `userbot/swarm_manager.py`, `run.py`.
- Unit/integration tests startup, reload и persisted quarantine.
- Основная спецификация `swarm-runtime` и README.
