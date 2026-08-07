## Why

Scheduled swarm exchange может бесконечно повторять один и тот же responder-turn, если Telegram запрещает аккаунту писать в целевую supergroup/channel. Сейчас `UserBannedInChannelError` выходит из `send_message`, оставляет exchange в статусе `started`, валит текущий scheduler tick и на следующем тике снова запускает Gemini для того же сообщения.

## What Changes

- Классифицировать постоянные Telegram send errors отдельно от временных/неожиданных ошибок.
- При постоянном запрете отправки отключать аккаунт из runtime-пула и сразу переназначать turn доступной персоне; если замены нет — завершать exchange как `skipped`, не роняя scheduler tick.
- Применить одинаковую защиту к initiator и responder отправкам.
- Сохранять сгенерированный initiator/responder text до Telegram send, чтобы retry после временной ошибки не вызывал LLM повторно.
- Оставить временные и неизвестные исключения пробрасываемыми для существующей observability/retry семантики.
- Добавить regression-тесты для permanent error, отсутствия повторной LLM-генерации и сохранения штатного успешного пути.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `swarm-runtime`: scheduled exchange устойчив к постоянным Telegram send restrictions и не выполняет повторную LLM-генерацию уже подготовленного текста.
- `message-persistence`: generated text сохраняется до сетевой отправки Telegram и может быть повторно использован при retry.

## Impact

- `userbot/orchestrator.py`
- `userbot/exchange_store.py`
- regression tests для orchestrator/exchange store
- SQLite schema получает nullable `responder_text`; миграция выполняется существующим idempotent `_ensure_column`.
