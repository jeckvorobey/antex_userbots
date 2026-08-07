## Why

Swarm запускает аккаунт после подключения и проверки membership, но не подтверждает глобальную пригодность аккаунта для messaging API. Замороженный или деактивированный аккаунт может остаться в конфигурации и повторно использоваться.

## What Changes

- До startup membership delay выполнять непубликуемую проверку глобальной доступности messaging API.
- При подтверждённой блокировке, деактивации или отзыве сессии отключать аккаунт до включения в active pool.
- Persistently сохранять global quarantine и логировать, что бот заморожен и требует внимания.

## Capabilities

### Modified Capabilities

- `swarm-runtime`: startup проверяет глобальную доступность messaging API и выводит замороженный аккаунт из runtime.

## Impact

- `userbot/client.py`
- `userbot/swarm_manager.py`
- `run.py`
- `tests/test_runtime.py`
- `tests/test_swarm_manager.py`
