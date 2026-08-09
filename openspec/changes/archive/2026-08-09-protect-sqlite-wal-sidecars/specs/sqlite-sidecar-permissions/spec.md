## ADDED Requirements

### Requirement: Owner-only права SQLite sidecar-файлов
Система SHALL ограничивать права основной SQLite БД и созданных WAL/SHM sidecar-файлов до `0600`.

#### Scenario: Запись создаёт WAL sidecar
- **WHEN** runtime записывает данные в file-backed SQLite БД с WAL
- **THEN** созданные `-wal` и `-shm` файлы SHALL иметь права `0600`
