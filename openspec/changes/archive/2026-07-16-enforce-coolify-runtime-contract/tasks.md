## 1. TDD: volume identity

- [x] 1.1 Добавить failing tests для valid Linux mountinfo + marker, отсутствующего mount, отсутствующего/mismatched/symlink marker и local `:memory:` bypass.
- [x] 1.2 Добавить failing integration test, что `_run_application` выполняет volume validation до handover delay, runtime lock и SQLite bootstrap.

## 2. TDD: bounded cleanup

- [x] 2.1 Добавить failing tests для timeout зависшего registered client и продолжения cleanup healthy clients.
- [x] 2.2 Добавить failing test для timeout незарегистрированного client при cancellation startup hook.
- [x] 2.3 Добавить failing tests для timeout одного SQLite resource, закрытия второго и последующего release runtime lock.

## 3. Реализация

- [x] 3.1 Реализовать Linux `RuntimeVolumeGuard` с `/proc/self/mountinfo`, regular non-symlink marker и точным сравнением `COOLIFY_RESOURCE_UUID` без логирования UUID.
- [x] 3.2 Встроить fail-closed volume validation в startup до handover delay/runtime lock/SQLite/Telegram.
- [x] 3.3 Ограничить client cleanup timeout 5 секундами для registered и partial-startup clients с best-effort продолжением.
- [x] 3.4 Ограничить SQLite resource close timeout 3 секундами и закрывать resources параллельно с best-effort продолжением.

## 4. Production contract и документация

- [x] 4.1 Добавить в README точную Coolify 4.1+ настройку Stop Grace Period 60 seconds и безопасную команду первичного создания marker.
- [x] 4.2 Обновить `openspec/project.md`, threat model и security diff report fail-closed volume invariant и рассчитанным shutdown budget.

## 5. Проверка и завершение

- [x] 5.1 Запустить узкие tests volume/lifecycle/swarm manager, затем полный `uv run pytest`.
- [x] 5.2 Выполнить `git diff --check`, `docker build --check .` и `openspec validate --strict --all`.
- [x] 5.3 Синхронизировать delta spec в `openspec/specs` и архивировать полностью выполненный change.
