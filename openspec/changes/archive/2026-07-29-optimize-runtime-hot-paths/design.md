## Context

Один процесс обслуживает несколько групп через 12 Telethon-клиентов. Router зарегистрирован на каждом клиенте, scheduler обходит группы последовательно, а prompt composition выполняется в latency-sensitive Telegram handlers. Оптимизации должны сохранить async-only runtime, точную адресность reply, group scope и последовательные scheduled операции.

## Goals / Non-Goals

**Goals:**

- Убрать ненужные async sender lookup и INFO-логи с non-reply hot path.
- Ограничить память и очередь addressed reply без накопления дополнительных 240-секундных интервалов.
- Обеспечить справедливый последовательный старт обхода групп.
- Убрать повторные синхронные чтения статических prompt/persona из event loop.
- Позволить SQLite использовать timestamp range индексы.

**Non-Goals:**

- Параллельные group orchestrator или Telegram join.
- Изменение startup membership и reload membership.
- Отдельное read-only SQLite connection.
- Изменение формата БД или Telegram-сообщений.

## Decisions

### Security hardening found during required review

- Validate prompt names as a single non-empty filename before resolving them below `prompts_dir`.
- Restrict filesystem-backed SQLite databases to owner read/write permissions (`0600`) on open.
- Keep the addressed-reply group allowlist fail-closed. Resolve target-only groups before handler registration and add only resolved numeric chat ids; an empty set rejects every event.
- Pin minimum fixed versions for runtime dependencies reported by `pip-audit`.

1. Router проверяет enabled group, swarm sender и `is_reply` до `_is_bot_sender`. Проверка Telegram bot остаётся обязательной только для reply-кандидатов.
2. Router хранит число pending replies на экземпляр, то есть на bot. Значение резервируется до ожидания human slot и освобождается в `finally`. При достижении `addressed_reply_max_pending_per_bot` новое событие отклоняется до Gemini.
3. Для принятого события фиксируется `reply_due_at = monotonic() + 240`. `_process_reply` после генерации ждёт только остаток до due time. Ожидание human slot больше не добавляет полный новый интервал.
4. `_ReplyRateLimiter` выполняет периодическую sweep-очистку. Истёкшие deque и их ключи удаляются не чаще одного раза за текущее rate-limit window, сохраняя амортизированную стоимость.
5. Scheduler хранит индекс следующей стартовой группы и циклически поворачивает snapshot `current_groups`. Внутри tick группы по-прежнему обрабатываются строго последовательно.
6. `AsyncTextFileCache` кэширует текст по `(mtime_ns, size)`, а `stat/read_text` выполняет через `asyncio.to_thread`. Отдельные cache-инстансы принадлежат `PromptLoader` и `PromptComposer`.
7. History timestamps уже сериализуются как sortable UTC `YYYY-MM-DD HH:MM:SS`, поэтому `created_at >= ? ORDER BY created_at, id` сохраняет хронологию и использует существующие composite indexes.

## Risks / Trade-offs

- [Pending limit отклонит reply при перегрузке] → логировать rejection и оставить default достаточно выше обычной активности.
- [Файл изменён без смены mtime/size] → файловая сигнатура соответствует обычным editor/deploy операциям; restart остаётся гарантированным fallback.
- [Round-robin меняет порядок групп между ticks] → порядок внутри каждого tick стабилен и последовательный, public cadence остаётся persisted.
- [Timestamp ordering отличается от insertion id для вручную импортированных данных] → контракт требует хронологический порядок, а UTC timestamp является корректным ключом.
