## Why

При 12 userbot-аккаунтах каждое обычное Telegram-сообщение проходит через router каждого клиента, создаёт лишние sender lookup и INFO-логи, а addressed reply могут накапливаться в неограниченной четырёхминутной очереди. Дополнительно scheduler всегда начинает с одной группы, а prompt/persona-файлы перечитываются с диска для каждой генерации.

## What Changes

- Отсекать non-reply события до sender lookup и логировать ожидаемые ignore-ветки на DEBUG.
- Ограничить число принятых, но ещё не завершённых addressed reply на одного bot.
- Считать четырёхминутный срок публикации от момента принятия события, чтобы ожидание human slot не добавляло новые четырёхминутные интервалы.
- Удалять истёкшие rate-limit buckets и не удерживать ключи неактивных отправителей весь lifetime процесса.
- Начинать последовательный scheduler tick с очередной группы по round-robin, не добавляя параллельные Gemini или Telegram операции.
- Кэшировать prompt/persona-файлы с автоматическим обновлением по файловой сигнатуре и выполнять файловое чтение вне event loop.
- Использовать индексируемое сравнение UTC timestamp для session history.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `addressed-reply-routing`: ранний отсев, bounded pending replies, абсолютный срок публикации и очистка rate-limit state.
- `runtime-configuration`: настраиваемый предел pending replies на одного bot.
- `swarm-runtime`: последовательный round-robin порядок групп scheduler.
- `prompt-and-gemini`: неблокирующий cache prompt/persona с обновлением при изменении файла.
- `message-persistence`: индексируемая временная фильтрация session history.

## Impact

- `userbot/reply_router.py`, `run.py`, `core/config.py`, `ai/gemini.py`, `ai/prompt_composer.py`, `ai/history.py`.
- Тесты router, runtime, config, prompt loading/composition и history.
- Основные OpenSpec specs, README и пример TOML.
- Внешние зависимости и формат SQLite не меняются.
