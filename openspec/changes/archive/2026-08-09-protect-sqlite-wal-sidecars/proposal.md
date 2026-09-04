## Why

SQLite WAL sidecar-файлы могут содержать историю сообщений и должны иметь те же owner-only права, что и основная БД.

## What Changes

- Ограничить права основной SQLite БД и её WAL/SHM sidecar-файлов до `0600` после каждой записи.

## Capabilities

### New Capabilities

- `sqlite-sidecar-permissions`: Защита файлов SQLite journal/WAL.

### Modified Capabilities

- Нет.

## Impact

- `storage/sqlite_database.py`, tests и security report.
