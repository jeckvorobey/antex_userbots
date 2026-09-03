## Why

Codex Review №2 выявил две runtime-регрессии: явно отключённые группы могут повторно активироваться через legacy fallback, а положительный raw Telegram ID не нормализуется в формат `event.chat_id`. Это приводит либо к нежелательной отправке сообщений, либо к молчаливому отклонению корректных addressed replies.

## What Changes

- Не создавать legacy fallback, если в актуальной конфигурации уже присутствует список `groups`, но все группы отключены.
- Нормализовать положительные raw ID групп через разрешённый Telegram entity до marked peer ID Telethon для allowlist addressed replies.
- Закрепить обе ветки регрессионными тестами и актуализировать runtime-контракты.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `swarm-runtime`: явно отключённые группы не должны повторно активироваться через legacy fallback.
- `addressed-reply-routing`: положительный raw ID должен преобразовываться в формат Telegram event peer ID.

## Impact

Изменения затрагивают `run.py`, runtime-тесты и соответствующие OpenSpec-контракты. Публичный формат конфигурации и зависимости не меняются.
