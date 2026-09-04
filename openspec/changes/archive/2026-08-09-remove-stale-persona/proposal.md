## Why

Локальная production-сессия и persona-файл, не входящие в текущий roster, нарушали его инвентарь.

## What Changes

- Удалить неиспользуемый persona-файл и локальный ключ сессии.

## Capabilities

### New Capabilities

- Нет.

### Modified Capabilities

- `production-personas`: Привести inventory persona-файлов к production roster.

## Impact

- Локальный `.env.prod` и `ai/prompts/bots/`.
