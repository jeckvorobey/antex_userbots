## Context

Startup availability snapshot и durable quarantine используют одну таблицу. Текущий reset удаляет все строки, а membership hook использует глобальную ошибку аккаунта и пропускает unresolved target. Reload обновляет список групп без проверки активных клиентов.

## Goals / Non-Goals

**Goals:**

- Сохранить durable quarantine до ручного снятия.
- Разделить global account failure и group availability failure.
- Активировать startup/reload группу только после успешной проверки всех затронутых клиентов.
- Не оставлять подключённые клиенты после частичного startup failure.

**Non-Goals:**

- Автоматически снимать durable quarantine.
- Перезапускать bot pool при изменении списка ботов.
- Менять Telegram retry policy или расписание exchange.

## Decisions

- `reset_startup_availability` удаляет только строки с `group_key='__startup__'`; остальные quarantine-записи считаются durable.
- Group-level отказ выражается отдельным `GroupAvailabilityError`, поэтому manager обрабатывает его как startup failure без global quarantine.
- Общий helper проверяет resolved target и `can_write is True`; startup hook требует успех для каждой enabled-группы.
- На reload проверяются новые и изменившиеся enabled-группы для каждого active bot. Группа включается в runtime только если все проверки успешны; иначе остаётся выключенной до следующего изменения конфигурации/restart.
- Generic startup failure выполняет best-effort stop и удаляет частично зарегистрированный client до записи failed state.

## Risks / Trade-offs

- Недоступная новая группа не начнёт работу после reload → лог содержит group id и безопасную категорию ошибки.
- Проверка reload добавляет Telegram-запросы → выполняется только для новых/изменённых enabled-групп и переиспользует dialog index на клиента.
- Cleanup stop сам может завершиться ошибкой → исходная startup-причина сохраняется, cleanup failure логируется без остановки обработки остальных профилей.
