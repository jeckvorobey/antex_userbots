## 1. Lifecycle TDD

- [x] 1.1 Добавить failing tests для эксклюзивного runtime-lock, ожидания второго экземпляра, timeout и `:memory:` режима.
- [x] 1.2 Добавить failing tests для `SIGTERM`/shutdown event и порядка закрытия scheduler, swarm, SQLite и runtime-lock.
- [x] 1.3 Добавить failing tests для отмены Telethon client во время startup hook и продолжения cleanup после ошибки stop одного клиента.

## 2. Persistence TDD

- [x] 2.1 Добавить failing tests для единого SQLite busy timeout в `MessageHistory` и `ExchangeStore`.
- [x] 2.2 Добавить failing tests для retry runtime bootstrap только при `database is locked` и закрытия частично созданных connections.

## 3. Implementation

- [x] 3.1 Реализовать асинхронно ожидаемый Linux runtime-lock рядом с effective SQLite path без внешних зависимостей.
- [x] 3.2 Реализовать handover delay, раннюю установку signal handlers и управляемую отмену swarm lifecycle в `run.py`.
- [x] 3.3 Расширить cleanup `SwarmManager`, чтобы он покрывал startup cancellation и пытался остановить все созданные clients.
- [x] 3.4 Добавить SQLite busy timeout и ограниченный lock-only bootstrap retry с логированием.
- [x] 3.5 Явно объявить `STOPSIGNAL SIGTERM` в Docker image.

## 4. Documentation and Validation

- [x] 4.1 Обновить `README.md` инструкциями Coolify: `/app/data`, rolling overlap, stop grace period и ожидаемая последовательность lifecycle-логов.
- [x] 4.2 Обновить `openspec/project.md` новым runtime ownership и graceful shutdown flow.
- [x] 4.3 Выполнить релевантные tests, полный `uv run pytest` и `openspec validate --strict --all`.
- [x] 4.4 Синхронизировать delta specs в `openspec/specs` и архивировать завершённый change.
