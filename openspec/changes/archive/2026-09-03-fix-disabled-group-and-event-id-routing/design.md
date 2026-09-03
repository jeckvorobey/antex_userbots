## Context

Настройки сохраняют legacy-поля `group_chat_id` и `group_target` для совместимости. При наличии нового `[[groups]]` эти поля также заполняются из первой группы, поэтому пустой `enabled_groups` нельзя использовать как признак отсутствия нового списка. Отдельно Telegram допускает положительный raw ID, но Telethon events используют marked peer ID.

## Goals / Non-Goals

**Goals:**

- Различать отсутствие нового списка групп и список, где все группы отключены.
- Формировать allowlist в том же ID namespace, что и `event.chat_id`.
- Сохранить реальную поддержку legacy-конфигурации.

**Non-Goals:**

- Менять TOML-схему или удалять legacy-поля.
- Переписывать общий алгоритм Telegram group resolution.

## Decisions

1. Legacy fallback разрешён только когда `settings.groups` отсутствует или пуст. Наличие хотя бы одной явно описанной группы делает `enabled_groups` единственным источником активности.
2. Для event allowlist сначала используется `resolved_target` и `telethon.utils.get_peer_id`. Fallback применяется только если entity отсутствует; уже отрицательный configured ID сохраняется, а положительный без entity не считается безопасно нормализованным.
3. Регрессионные тесты проверяют публичные helper-контракты без внешних Telegram-вызовов.

## Risks / Trade-offs

- [Legacy settings object может не иметь `groups`] → использовать безопасный `getattr` и сохранить прежний fallback.
- [Положительный ID без resolved entity неоднозначен между basic chat и channel] → не угадывать namespace; startup resolution обязан предоставить entity.

## Migration Plan

Миграция данных не требуется. Откат выполняется возвратом одного runtime-коммита.

## Open Questions

Нет.
