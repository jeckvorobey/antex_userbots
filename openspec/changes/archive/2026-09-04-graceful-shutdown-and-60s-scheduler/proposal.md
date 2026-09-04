## Why

Остановка процесса через Ctrl+C сейчас завершается пользовательской трассировкой `CancelledError`/`KeyboardInterrupt`, хотя отмена supervisor-задач является штатной частью shutdown. Одновременно рабочая конфигурация запускает scheduler каждые 30 секунд, тогда как требуемый интервал составляет 60 секунд.

## What Changes

- Обрабатывать Ctrl+C в точке входа как штатную остановку без traceback.
- Сохранить отмену supervisor-задач и полное освобождение scheduler, Telegram-клиентов, AI-клиента и SQLite runtime.
- Изменить стандартный и production-интервал scheduler с 30 на 60 секунд.
- Обновить тесты и документацию конфигурации.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `swarm-runtime`: штатная остановка процесса по Ctrl+C и стандартный 60-секундный scheduler tick.

## Impact

Изменяются точка входа `run.py`, модель конфигурации, TOML-конфигурации, runtime-тесты, основной swarm runtime spec и README. Внешние зависимости и форматы данных не меняются.
