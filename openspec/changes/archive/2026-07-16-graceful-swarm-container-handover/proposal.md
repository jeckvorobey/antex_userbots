## Why

Coolify rolling deployment кратковременно запускает новый контейнер до остановки старого. Текущий процесс не обрабатывает `SIGTERM` как запрос на graceful shutdown, а новый экземпляр сразу открывает общий SQLite-файл и Telegram-сессии, поэтому возможны `sqlite3.OperationalError: database is locked`, параллельное использование одинаковых Telethon-сессий и незакрытые клиенты при остановке во время долгого startup.

## What Changes

- Добавить межпроцессное владение swarm runtime через эксклюзивный файловый lock рядом с SQLite-базой; до получения lock новый экземпляр не открывает SQLite и не подключает Telegram-клиенты.
- Добавить короткую startup handover-паузу и ограниченное ожидание lock, чтобы первый деплой новой версии безопасно пережил перекрытие со старой версией, которая ещё не умеет держать runtime-lock.
- Обрабатывать `SIGTERM` и `SIGINT` как управляемую остановку: прекратить scheduler, отменить startup/supervise задачи, отключить Telethon-клиенты, закрыть SQLite-соединения и только затем освободить runtime-lock.
- Гарантировать очистку Telethon-клиента, если остановка или ошибка произошла во время долгого startup hook до регистрации клиента в активном пуле.
- Увеличить SQLite busy timeout и добавить ограниченный retry bootstrap-операций при временном `SQLITE_BUSY`/`SQLITE_LOCKED`.
- Добавить TDD-покрытие контейнерного handover, сигнальной остановки, startup cancellation и временной SQLite-блокировки; документировать настройки Coolify и путь persistent storage.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `swarm-runtime`: процесс получает эксклюзивное runtime-владение до открытия внешних ресурсов и гарантированно освобождает Telegram/SQLite ресурсы при `SIGTERM`, включая остановку во время startup.
- `message-persistence`: SQLite bootstrap ожидает кратковременную блокировку и не выполняется параллельно двумя swarm-процессами, использующими одну базу.

## Impact

- Runtime-код: `run.py`, `userbot/swarm_manager.py`, новый небольшой модуль lifecycle-lock в `core/`.
- Persistence: параметры подключения в `ai/history.py` и `userbot/exchange_store.py`, без изменения схемы или формата данных.
- Container/deployment: `Dockerfile`, Coolify stop grace period и persistent volume с общим lock-файлом рядом с `data/history.db`.
- Tests/docs: `tests/test_runtime.py`, `tests/test_swarm_manager.py`, persistence tests, `README.md`, `openspec/project.md` и основные OpenSpec specs.
- Новых внешних сервисов и зависимостей нет; используется Linux `flock` из стандартной библиотеки Python.
