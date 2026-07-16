## Context

Coolify запускает новый container до удаления старого. В предоставленном production-логе новый container перешёл в `Started` в `07:02:05.154`, а удаление старых началось в `07:02:05.260`. При этом текущий `run.py` открывает две долгоживущие `aiosqlite`-сессии до запуска swarm, не устанавливает обработчик `SIGTERM`, а `SwarmManager.start()` последовательно запускает 12 Telethon-клиентов и может по 1–3 минуты находиться в startup hook каждого клиента.

Существующий `finally` закрывает scheduler и SQLite только при штатном выходе из `_run_swarm_mode`. Docker `SIGTERM` сейчас завершает процесс по умолчанию, а отмена во время `manager.start()` может произойти до входа в блок `try/finally`. Дополнительно `_start_single_bot()` регистрирует client только после долгого startup hook, поэтому отменённый в этот момент client недоступен для `manager.stop()`.

Проект ограничен одним процессом swarm на одну SQLite-базу, Linux container runtime, `aiosqlite`, Telethon и отсутствием HTTP-сервера. Новые внешние coordination services добавлять нельзя.

## Goals / Non-Goals

**Goals:**

- Не допускать параллельного открытия SQLite и одинаковых Telegram string sessions двумя containers, использующими один persistent volume.
- Обрабатывать `SIGTERM`/`SIGINT` как запрос на управляемую остановку всего lifecycle, включая долгий startup.
- Освобождать ресурсы в порядке: scheduler → startup/supervise tasks → Telethon clients → SQLite connections → runtime lock.
- Переживать короткую legacy-фазу первого deploy, когда старый container ещё не умеет держать новый lock.
- Переживать временный внешний SQLite write-lock через busy timeout и ограниченный bootstrap retry.

**Non-Goals:**

- Не поддерживать несколько одновременно активных swarm replicas на одной SQLite-базе.
- Не добавлять Redis, PostgreSQL, HTTP health endpoint или отдельный coordinator service.
- Не менять Telegram routing, расписание exchanges, prompts, схему SQLite или формат persisted data.
- Не гарантировать `flock` на сетевых файловых системах с несовместимой семантикой блокировок; production volume должен быть локальным Docker storage или bind mount на одном host.

## Decisions

### Эксклюзивный runtime lock рядом с SQLite

Новый `RuntimeInstanceLock` будет использовать Linux `fcntl.flock(LOCK_EX | LOCK_NB)` на файле `<db_path>.runtime.lock`. Lock берётся до `MessageHistory.init_db()` и до создания Telethon clients и удерживается до полного закрытия runtime. Ожидание выполняется асинхронным polling с ограниченным timeout и явным логированием. Для `:memory:` lock является no-op.

Файл lock располагается рядом с базой, чтобы автоматически использовать тот же Coolify persistent volume. Он открывается с запретом перехода по symbolic link, проверяется как обычный файл и получает режим `0600`, чтобы подмена пути не приводила к изменению другого доступного файла. Наличие пустого lock-файла после остановки нормально: владение определяется kernel lock на открытом file descriptor, а не существованием файла.

Альтернативы:

- Только `sleep`: уменьшает вероятность гонки, но не доказывает, что старый процесс завершён.
- Только SQLite busy timeout: защищает отдельный write, но не предотвращает одновременное подключение одинаковых Telethon sessions.
- PID-файл: устаревает после `SIGKILL` и требует ненадёжной очистки.
- Redis lease: нарушает ограничение проекта и добавляет внешний dependency.

### Короткая handover-пауза перед первой попыткой владения

До открытия SQLite процесс ждёт короткую фиксированную паузу. Она нужна только для первого rollout новой версии: старый image ещё не держит runtime lock, поэтому новый image смог бы получить lock немедленно. После первого rollout основную гарантию даёт `flock`, а пауза остаётся небольшим детерминированным buffer для Coolify container replacement.

### Сигнальная остановка через asyncio event

`main()` установит обработчики `SIGTERM` и `SIGINT` до handover-паузы и ожидания lock. Основной swarm будет выполняться как task одновременно с ожиданием shutdown event. При сигнале scheduler перестаёт создавать новые jobs, swarm task отменяется и ожидается, затем закрываются SQLite-сессии и освобождается runtime lock. Обработчики сигналов удаляются в финале.

`_run_swarm_mode()` оборачивает весь lifetime `SwarmManager`, включая `manager.start()`, в `try/finally`. `_start_single_bot()` останавливает локально созданный client при любой ошибке или отмене до его успешной регистрации. `SwarmManager.stop()` пытается остановить все известные clients, даже если остановка одного завершилась ошибкой.

### SQLite busy timeout и bootstrap retry

Оба `aiosqlite.connect()` получают одинаковый ненулевой busy timeout. `_build_runtime_context()` повторяет весь bootstrap только для сообщений `database is locked`/`database table is locked`, предварительно закрывая частично созданные connections. Другие `OperationalError` не маскируются. Число повторов и задержки ограничены константами, чтобы container не зависал бесконечно.

### Coolify contract

Docker image явно объявляет `STOPSIGNAL SIGTERM`. README фиксирует destination persistent volume `/app/data`, поскольку effective `db_path` равен `data/history.db` при `WORKDIR /app`, и stop grace period не менее 30 секунд. Для worker без HTTP routing не добавляется фиктивный HTTP health server.

## Risks / Trade-offs

- [Старый image не держит runtime lock при первом rollout] → короткая startup-пауза и SQLite bootstrap retry покрывают переходный deploy; при необходимости первый deploy можно выполнить после ручной остановки.
- [Coolify отправит `SIGKILL` до завершения cleanup] → cleanup ограничен локальными disconnect/close операциями, Docker image объявляет `SIGTERM`, документация требует stop grace не менее 30 секунд; kernel всё равно освободит `flock` и SQLite locks при `SIGKILL`.
- [Lock-файл не находится на общем volume] → README фиксирует `/app/data`; startup log выводит эффективные DB и lock paths без секретов.
- [Сетевой/NFS volume некорректно реализует `flock`] → такие volume не рекомендуются для этой SQLite deployment topology.
- [Остановка во время Gemini/Telegram operation] → scheduler останавливается первым, tasks отменяются, а затем clients/connections закрываются; незавершённая операция может быть отменена, но новый process не стартует до освобождения lock.
- [Ожидание lock превышает deployment timeout] → ожидание ограничено и завершается понятной ошибкой с lock path и timeout.

## Migration Plan

1. Собрать и протестировать image с lifecycle lock, signal handling и SQLite retry.
2. Проверить, что Coolify persistent volume смонтирован в `/app/data`, а stop grace period составляет не менее 30 секунд.
3. Первый rollout выполнить обычным способом; startup delay покрывает короткое перекрытие со старым image. Для максимально безопасного перехода допустима предварительная ручная остановка старого container.
4. В логах проверить последовательность: ожидание handover → получение runtime lock → SQLite bootstrap → Telegram startup. При следующем deploy проверить: `SIGTERM` → остановка clients → закрытие SQLite → освобождение lock → получение lock новым container.
5. Rollback на старый image возможен без миграции данных, поскольку схема SQLite не меняется. Перед rollback старый container нужно остановить, так как rollback image не понимает runtime lock.

## Open Questions

Нет блокирующих вопросов. Значения задержек остаются внутренними безопасными defaults и могут стать TOML-настройками только при подтверждённой operational необходимости.
