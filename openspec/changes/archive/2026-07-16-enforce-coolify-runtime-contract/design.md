## Context

Coolify rolling deployment кратковременно держит old/new containers одновременно. Уже реализованный `flock` предотвращает двойной runtime только при общем persistent volume, а текущий cleanup не имеет hard deadline внутри `client.stop()`/SQLite `close()`. Production log показывает `docker stop --time=30`; Coolify 4.1.0 добавил per-application `stop_grace_period` в `Advanced → Operations`, а официальный storage contract требует явно заданный destination `/app/data`.

Пользователь подтвердил single-host topology, локальный Docker volume/bind mount, отсутствие посторонних writers и доверенный Coolify host. Поэтому цель — превратить две operator assumptions в проверяемые fail-closed invariants, не добавляя coordinator/service.

## Goals / Non-Goals

**Goals:**

- До SQLite/Telegram доказать, что effective DB находится на реально смонтированном `/app/data` и marker принадлежит текущему Coolify resource UUID.
- Не создавать marker автоматически: неверный/пустой volume должен завершать startup, а не становиться новой production БД.
- Ограничить worst-case cleanup зависших Telethon/SQLite ресурсов с достаточным запасом относительно наблюдаемого 30-second Docker stop timeout.
- Сохранить best-effort cleanup остальных ресурсов и release kernel lock при единичном timeout/error.
- Дать безопасный порядок миграции без удаления/переноса SQLite.

**Non-Goals:**

- Поддержка NFS, multi-host replicas или нескольких постоянно активных swarm runtimes.
- Изменение SQLite schema или перенос на server database.
- Управление Coolify через API из приложения или хранение Coolify API token в container.
- Автоматическое исправление неверного mount: startup только диагностирует и fail-closed.

## Decisions

### Проверять kernel mount table, а не только существование директории

Guard вычисляет absolute DB parent и для production path требует ровно `/app/data`. Наличие mount point проверяется по `/proc/self/mountinfo`, что корректно различает Docker volume и bind mount даже когда bind использует тот же filesystem; простая проверка `Path.exists()` приняла бы директорию из image, а `os.path.ismount()` не гарантирует обнаружение same-filesystem bind mounts.

Альтернатива — полагаться только на Coolify UI. Она не даёт runtime evidence и сохраняет silent creation `data/history.db` внутри ephemeral image layer.

### Marker связывает volume с `COOLIFY_RESOURCE_UUID`

На корректном уже подключённом volume оператор один раз создаёт `/app/data/.coolify-resource-uuid` со значением predefined runtime variable `COOLIFY_RESOURCE_UUID`. Guard требует regular non-symlink marker, точное совпадение непустого значения и не выводит UUID в error/log. Marker не считается секретом, но имеет mode `0600`.

Автоматически создавать marker нельзя: при случайно пустом/wrong volume это закрепило бы ошибку. UUID стабилен для одного Coolify resource и меняется при clone, поэтому clone не должен молча использовать исходный state.

Альтернатива — marker со случайным отдельным secret. Она дублирует уже предоставляемый Coolify identity и усложняет rotation без усиления рассматриваемой single-host модели.

### Cleanup ограничен per-resource deadlines

Каждый Telethon `stop()` получает timeout 5 секунд, все registered clients останавливаются параллельно. Cleanup незарегистрированного startup client также ограничен 5 секундами. Оба SQLite resources закрываются параллельно с timeout 3 секунды каждый. Timeout/error логируется, но не останавливает cleanup остальных ресурсов.

Worst-case signal во время startup: 5 секунд на текущий client + 5 секунд на registered clients + 3 секунды на SQLite resources, то есть около 13 секунд плюс небольшой scheduler/process overhead. Это оставляет существенный запас относительно наблюдаемого/default Coolify timeout 30 секунд; production setting фиксируется на 60 секунд.

Альтернатива — один global `asyncio.timeout`. Он хуже локализует зависший ресурс и может отменить весь cleanup до попытки закрыть остальные connections.

### Coolify stop grace остаётся platform setting

Dockerfile может задать signal, но не длительность grace period. Для Coolify 4.1+ оператор выставляет 60 секунд в `Advanced → Operations → Stop Grace Period`; приложение не получает подтверждённое значение этого UI field и не будет использовать выдуманную environment variable.

## Risks / Trade-offs

- [Marker не создан перед первым deploy] → новый container fail-closed; migration plan создаёт marker в ещё работающем old container до rollout.
- [Coolify clone получает новый UUID и копию volume] → startup fail-closed до осознанного обновления marker; это защищает от случайного двойного использования sessions.
- [Kernel mountinfo недоступен] → startup fail-closed в Coolify container; production Linux предоставляет `/proc/self/mountinfo`, тесты используют отдельный fixture.
- [Resource timeout отменяет cleanup coroutine, но библиотека не освобождает socket немедленно] → процесс всё равно завершится задолго до Docker deadline; kernel закроет descriptors, runtime lock освобождается при exit.
- [Operator выставил grace меньше 13 секунд] → код не может запретить внешний `SIGKILL`; README требует 60 секунд, а production log после настройки должен показать `docker stop --time=60`.

## Migration Plan

1. Не останавливая текущий container, открыть Coolify Terminal приложения и проверить непустой `COOLIFY_RESOURCE_UUID`.
2. В текущем container создать marker атомарной заменой temporary file, установить mode `0600`, сверить содержимое без публикации UUID в общие логи.
3. В Coolify 4.1+ открыть `Advanced → Operations`, установить Stop Grace Period `60` seconds и сохранить.
4. Выполнить deploy новой версии. Проверить логи: volume validation → handover wait → runtime lock → SQLite → Telegram.
5. На следующем deploy проверить `SIGTERM` и полное завершение существенно раньше 60 секунд; deployment log должен использовать timeout 60.

Rollback: вернуть предыдущий image можно без DB migration; marker остаётся безопасным служебным файлом. Stop grace 60 можно оставить. Если guard блокирует startup из-за реальной ошибки mount, исправить Coolify storage вместо удаления marker или создания новой БД.

## Open Questions

Нет. Production topology и trust assumptions подтверждены пользователем.
