## Context

Runtime использует SQLite WAL и хранит сообщения локально.

## Goals / Non-Goals

**Goals:**

- Ограничить доступ к SQLite-файлам владельцем процесса.

**Non-Goals:**

- Не менять схему БД или transaction model.

## Decisions

- После успешной записи chmod основную БД и существующие `-wal`/`-shm` файлы в `0600`.

## Risks / Trade-offs

- [Дополнительные filesystem stat/chmod] → только после записи и только для трёх файлов.
