# Отчёт security review незакоммиченного diff

## Резюме

Проверен только текущий незакоммиченный diff и непосредственно связанные runtime-файлы. Найдены и исправлены четыре замечания средней важности. После обязательной production-миграции marker и Stop Grace Period подтверждённых рисков уровня Medium, High или Critical в повторной проверке не остаётся.

Проект является Python worker без HTTP-фреймворка, поэтому в локальном skill-каталоге не было matching framework reference. Проверка опиралась на общие практики Python/Linux, официальную документацию [Python `os`](https://docs.python.org/3/library/os.html), [Dockerfile](https://docs.docker.com/reference/dockerfile), [Docker Compose lifecycle](https://docs.docker.com/reference/compose-file/services/#stop_grace_period) и [SQLite locking](https://www.sqlite.org/lockingv3.html).

## Исправленные замечания

### SEC-001 — Medium — переход по symbolic link при открытии runtime-lock

До исправления предсказуемый lock path открывался с `O_CREAT | O_RDWR`, поэтому процесс с правом записи в shared volume мог подменить его symbolic link и заставить startup обнулить другой доступный файл.

Исправление: `core/runtime_lock.py:RuntimeInstanceLock.acquire` открывает lock с `O_NOFOLLOW`/`O_CLOEXEC`, проверяет `fstat()` как regular file и устанавливает режим `0600` до `flock`. Регрессионный тест: `tests/test_runtime_lifecycle.py:test_runtime_lock_does_not_follow_symbolic_link`.

### SEC-002 — Medium — маскировка исходной bootstrap-ошибки при cleanup

До исправления исключение из `history.close()` заменяло исходный `database is locked` и прекращало cleanup до закрытия `ExchangeStore`. Это ухудшало диагностику и могло удерживать частично созданное соединение до завершения процесса.

Исправление: `run.py:_build_runtime_context_once` закрывает все созданные persistence-ресурсы через best-effort `gather`, отдельно логирует cleanup failures и повторно поднимает исходное исключение. Регрессионный тест: `tests/test_runtime_lifecycle.py:test_runtime_context_once_preserves_bootstrap_error_when_cleanup_fails`.

### SEC-003 — Medium — разные mounts обходят единый runtime lock

До исправления old/new containers могли получить разные `/app/data`: каждый создавал собственный lock и SQLite, после чего оба подключали одинаковые Telethon sessions. Наличие каталога не доказывало, что persistent storage действительно смонтирован.

Исправление: `core/runtime_volume.py:RuntimeVolumeGuard` до handover delay, runtime lock, SQLite и Telegram проверяет `/app/data` в `/proc/self/mountinfo`, regular non-symlink marker и точное совпадение marker с непустым `COOLIFY_RESOURCE_UUID`. Marker не создаётся автоматически, UUID не логируется. Регрессионные тесты: `tests/test_runtime_lifecycle.py` для valid/missing mount, missing/empty/mismatched/symlink marker и порядка startup.

### SEC-004 — Medium — зависший cleanup мог пережить stop grace period

До исправления один `client.stop()` или SQLite `close()` мог ждать без верхней границы, после чего Coolify/Docker посылал бы `SIGKILL` и обрывал остальной cleanup.

Исправление: `userbot/swarm_manager.py:SwarmManager._stop_client` ограничивает registered и partial-startup Telethon cleanup пятью секундами и продолжает остановку остальных clients. `run.py:_close_runtime_resources` закрывает оба SQLite resource параллельно с трёхсекундным deadline. Worst-case внутренний budget около 13 секунд; production contract задаёт Coolify Stop Grace Period 60 секунд.

## Проверенные контроли

- контейнер продолжает работать от непривилегированного `appuser` (`Dockerfile:25`–`Dockerfile:29`);
- exec-form `CMD` и `STOPSIGNAL SIGTERM` позволяют Python-процессу получать lifecycle signal (`Dockerfile:31`–`Dockerfile:33`);
- runtime lock берётся до SQLite и Telegram, а освобождается после их cleanup;
- production volume identity проверяется до handover delay и runtime lock; неверный mount/marker приводит к fail-closed startup без новой SQLite;
- timeout одного Telethon/SQLite resource не прерывает попытки cleanup остальных ресурсов;
- SQLite retry ограничен только временными lock errors и имеет конечное число попыток;
- новые зависимости и реальные секреты в diff не добавлены;
- SQLite/lock volume явно ограничен локальным single-host storage (`README.md:261`–`README.md:270`).

## Остаточные риски

1. До первого deploy новой версии оператор должен создать marker на текущем production volume и сохранить Coolify Stop Grace Period 60 секунд. Приложение может проверить marker, но не может прочитать значение platform UI; неверная последовательность безопасно остановит новый container.
2. Тот, кто осознанно скопирует корректный marker вместе с данными на другой mount, может обойти identity check. При подтверждённой модели с доверенным Coolify admin и без посторонних writers это Low operational risk.
3. Гарантии `SQLite`, `flock` и mount guard предполагают локальный Linux Docker volume или bind mount. Для NFS/network filesystem эта схема не считается безопасной.
4. Инструмент `codex-security:security-diff-scan` в текущей сессии недоступен. Выполнен ручной diff-scan по тем же категориям, но без tool-generated coverage ledger; это не заявляется как полный repository-wide аудит.

## Проверки

- `uv run pytest -q` — 220 passed;
- `openspec validate --strict --all` — 7 passed после sync/archive, активных changes нет;
- `docker build --check .` — warnings отсутствуют;
- `git diff --check` — ошибок нет;
- complexity scanner — новых подтверждённых hotspots в diff нет.
