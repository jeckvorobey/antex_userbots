## Why

Сейчас scheduled exchange уже выбирает ботов с учётом `group_id` и `group_chat_id`, но anti-repeat cooldown исключает только последних трёх участников. Из-за этого в одной и той же группе одни и те же боты могут возвращаться в обмен слишком быстро, хотя пользователь хочет расширить локальную group-scoped ротацию до последних четырёх участников.

## What Changes

- Изменить правило выбора пары для scheduled exchange: при наличии достаточного пула не учитывать последних четырёх уникальных ботов, которые последними задавали вопрос или отвечали в текущей группе.
- Сохранить текущую деградацию cooldown: если после исключения последних четырёх участников в группе остаётся меньше двух кандидатов, orchestrator постепенно ослабляет фильтр, чтобы обмен всё равно мог быть создан.
- Уточнить OpenSpec-контракт, что recent-bot cooldown считается только по событиям scheduled exchange в пределах текущей группы, а не глобально по всем группам.
- Добавить тестовое покрытие на новый размер cooldown и на то, что история другой группы не влияет на выбор пары.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `scheduled-exchanges`: recent-bot anti-repeat for pair selection changes from the last three scheduled bot ids to the last four scheduled bot ids within the current group.

## Impact

- Затронуты `userbot/orchestrator.py` и тесты scheduled exchange выбора.
- Возможны точечные изменения в `userbot/exchange_store.py` тестах или OpenSpec delta spec, если потребуется явно зафиксировать group-scoped источник recent bot history.
- Публичные API, конфигурация, формат данных и SQLite schema не меняются.
