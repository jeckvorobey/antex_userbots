## Why

Runtime lock защищает SQLite и Telethon только когда rolling containers действительно используют один и тот же persistent volume, а graceful shutdown успевает завершиться до `SIGKILL`. Сейчас оба условия задокументированы, но приложение не проверяет mount identity и не ограничивает максимальную длительность cleanup, поэтому ошибки Coolify-конфигурации остаются операционным риском.

## What Changes

- **BREAKING**: при запуске внутри Coolify с effective DB path `/app/data/history.db` приложение будет fail-closed до SQLite/Telegram, если `/app/data` не является отдельным mount point или marker `.coolify-resource-uuid` отсутствует/не совпадает с `COOLIFY_RESOURCE_UUID`.
- Добавить отдельный runtime volume guard без автоматического создания marker, чтобы неверный или пустой mount нельзя было незаметно принять за production storage.
- Ограничить время disconnect каждого Telethon client и закрытия каждого SQLite resource; timeout одного ресурса не должен мешать cleanup остальных и освобождению runtime lock.
- Зафиксировать Coolify 4.1+ настройку `Advanced → Operations → Stop Grace Period = 60 seconds` и безопасную последовательность первичного создания marker на уже подключённом volume.
- Добавить TDD-покрытие mount/marker validation, cleanup timeouts и продолжения shutdown после зависшего ресурса.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `swarm-runtime`: startup получает fail-closed Coolify volume validation, а graceful shutdown — измеримые per-resource deadlines меньше production stop grace period.

## Impact

- Код: новый guard в `core/`, lifecycle в `run.py`, client cleanup в `userbot/swarm_manager.py`.
- Конфигурация production: marker на `/app/data` и Coolify application stop grace period 60 секунд.
- Документация/безопасность: `README.md`, `openspec/project.md`, threat model и security diff report.
- Данные/схема БД: не изменяются.
- Новые зависимости и внешние сервисы: отсутствуют.
