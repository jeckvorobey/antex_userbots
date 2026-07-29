## Why

`MessageHistory` и `ExchangeStore` сейчас открывают независимые соединения к одному файлу SQLite и отдельно фиксируют записи. Параллельная работа runtime может приводить к `sqlite3.OperationalError: database is locked`, включая кратковременную блокировку при запуске контейнера.

## What Changes

- Добавить общую runtime-зависимость `SQLiteDatabase`, владеющую единственным `aiosqlite.Connection`.
- Настраивать соединение через WAL, `synchronous=NORMAL`, `busy_timeout=30000`, `foreign_keys=ON` и `timeout=30`.
- Сериализовать все чтения, DDL/DML-записи и их `commit` одним `asyncio.Lock`, чтобы чтение не пересекалось с незавершённой write-транзакцией.
- Повторять только временные ошибки блокировки SQLite в пределах пяти общих попыток с четырьмя заданными задержками и логированием.
- Передавать общую базу в `MessageHistory` и `ExchangeStore`, не меняя таблицы, данные, запросы чтения и бизнес-логику.
- Инициализировать и закрывать общее соединение ровно один раз за lifecycle приложения.
- Покрыть конкурентные записи, pruning, стартовую блокировку и неизвестные `OperationalError` тестами и стресс-проверкой.

## Capabilities

### New Capabilities

- Отсутствуют.

### Modified Capabilities

- `message-persistence`: единое соединение, общий lock, PRAGMA-настройки и retry-контракт для общей SQLite persistence.
- `swarm-runtime`: lifecycle runtime создаёт и закрывает одно общее SQLite-соединение.

## Impact

Изменяются `storage/sqlite_database.py`, `ai/history.py`, `userbot/exchange_store.py`, `run.py`, тесты persistence/runtime и связанная документация. Путь `data/history.db`, схема таблиц и публичная бизнес-логика остаются без изменений.
