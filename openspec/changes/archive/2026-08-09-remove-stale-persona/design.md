## Context

Текущий `settings.prod.toml` не ссылался на один из локальных session key и persona-файлов, но они остались в workspace.

## Goals / Non-Goals

**Goals:**

- Удалить только подтверждённые неиспользуемые артефакты.
- Не раскрывать значение session string.

**Non-Goals:**

- Не менять roster активных ботов и другие personas.

## Decisions

- Ключ session удаляется по точному имени без вывода его значения.

## Risks / Trade-offs

- [Локальная сессия больше недоступна] → Удаляется по явному запросу и не используется production settings.
