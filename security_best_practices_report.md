# Security Best Practices Report

## Executive Summary

Проверен Python 3.11 swarm-runtime с Telethon, aiosqlite и Gemini SDK. Подтверждённая проблема с правами SQLite WAL/SHM исправлена и покрыта тестом.

## High

### SEC-01: WAL/SHM sidecar-файлы могли иметь более широкие права — исправлено

**Impact:** SQLite WAL и SHM могут содержать историю сообщений, поэтому права шире owner-only раскрывают локальные данные другим пользователям хоста.

- **Location:** `storage/sqlite_database.py:47`, `storage/sqlite_database.py:167`.
- **Fix:** после успешной записи runtime применяет `0600` к основной БД и существующим `-wal`/`-shm` файлам.
- **Verification:** `tests/test_sqlite_database.py::test_sqlite_database_restricts_wal_sidecar_permissions_after_write`.

## Medium and Low

Подтверждённых неустранённых находок нет. SQL-запросы параметризованы, invite links редактируются в критичных логах, а текст для Gemini и Telegram проходит существующую sanitization/output-safety проверку.

## Повторная проверка

- Статический поиск не обнаружил в runtime-коде `eval`, `exec`, небезопасную deserialization или shell-вызовы.
- Проверка tracked-файлов не обнаружила фактических значений session/API/Gemini secrets.
- `pip-audit` по экспортированным внешним production-зависимостям завершился без известных уязвимостей.
- Целевые security-тесты прошли: 80 passed.
- SEC-01 остаётся закрытой: после записи права основной SQLite БД, WAL и SHM принудительно ограничиваются до `0600`.
