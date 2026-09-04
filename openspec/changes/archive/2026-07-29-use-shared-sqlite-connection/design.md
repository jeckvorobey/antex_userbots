## Context

`MessageHistory` и `ExchangeStore` используют один файл, но владеют разными `aiosqlite.Connection`. Их транзакции могут пересекаться между coroutine и конкурировать за file lock. Runtime уже объединяет оба компонента в `RuntimeContext`, поэтому там естественно разместить ownership общего соединения.

## Goals / Non-Goals

**Goals:**

- Одно соединение и один write lock на runtime.
- Единая настройка SQLite и ограниченный retry только для временной блокировки.
- Retry охватывает DML, DDL и commit как одну повторяемую операцию.
- Существующие таблицы, запросы чтения и бизнес-результаты остаются прежними.

**Non-Goals:**

- Изменение схемы или пути базы.
- Удаление либо пересоздание файлов SQLite.
- Добавление другого хранилища или синхронного SQLite API.

## Decisions

1. `SQLiteDatabase` владеет connection и lock. `open()` создаёт родительскую директорию, вызывает `aiosqlite.connect(path, timeout=30)`, устанавливает row factory и PRAGMA. Альтернатива с отдельным lock в каждом store не защищает транзакции между компонентами.
2. Компоненты получают уже созданный `SQLiteDatabase` через constructor injection. Чтения используют `fetch_one` / `fetch_all` под общим lock, а записи держат тот же lock до успешного commit. Это не позволяет другой coroutine прочитать промежуточное состояние write-транзакции на том же соединении.
3. Retry принимает именованную async-операцию, ловит только `aiosqlite.OperationalError` с текстом `database is locked` или `database table is locked`, делает максимум пять общих попыток с паузами `0.2, 0.5, 1, 2` между ними и логирует следующую попытку. Неизвестные ошибки немедленно пробрасываются.
4. DDL и миграционные проверки выполняются внутри одной locked retry-операции каждого `init_db`, чтобы проверка колонок и последующие `ALTER`/индексы были согласованы.
5. `RuntimeContext.close()` закрывает только `SQLiteDatabase`. `MessageHistory` и `ExchangeStore` больше не владеют lifecycle соединения.

## Risks / Trade-offs

- [Долгая операция задерживает остальные обращения к connection] → общий lock охватывает только короткие SQLite-вызовы и обеспечивает изоляцию coroutine на одном соединении.
- [Повтор после частично исполненной транзакции] → перед retry выполняется rollback; DDL остаётся idempotent через `IF NOT EXISTS` и проверку колонок.
- [Ошибка во время построения runtime оставит connection открытым] → `_build_runtime_context` закрывает database при исключении до возврата context.
- [Тесты создавали stores по пути] → fixtures явно создают общую database; compatibility-конструктор не сохраняется, чтобы ownership был однозначным.

## Migration Plan

Деплой не меняет формат `data/history.db`. При старте новое соединение применяет PRAGMA и запускает существующие idempotent migrations. Rollback к предыдущему коду читает те же таблицы и данные.

## Open Questions

Нет.
