## Context

Review threads накопились на нескольких последовательных коммитах PR #18. Часть ранних замечаний уже исправлена, но 18 сценариев остаются воспроизводимыми: package discovery не включает `storage`, несколько lifecycle операций выполняются в небезопасном порядке, reload не поддерживает pending retry и актуальные security/group данные, а important-service логика частично захардкожена и не гарантирует responder turn.

## Goals / Non-Goals

**Goals:**

- Закрыть все подтверждённые actionable threads с regression coverage.
- Сохранить async-only runtime и существующие публичные сценарии swarm.
- Сделать ошибки persistence/network fail-safe без утечки секретов и invite hash.

**Non-Goals:**

- Не менять cadence important-service или Telegram session format; schema SQLite расширяется только обратно совместимым полем.
- Не добавлять HTTP server, новые внешние сервисы или sync I/O.
- Не перерабатывать архитектуру вне затронутых review paths.

## Decisions

1. Package discovery явно включает `storage*`; wheel test проверяет импорт из установленного артефакта.
2. Общий proxy валидируется на пересечении возможностей Telethon и HTTPX: `http`, `https`, `socks5`, `socks5h`. `socks4` отклоняется при загрузке settings.
3. Telegram invite определяется через case-insensitive parse scheme/host/path. Persisted group chat id использует marked peer id resolved entity, совпадающий с `event.chat_id`.
4. Startup snapshot failure откатывает только что активированный клиент. Global quarantine сначала удаляет аккаунт из active pool и сохраняет durable quarantine, затем best-effort обновляет transient snapshot.
5. `disable_bot` получает режим deferred disconnect: active state меняется синхронно, а stop запускается на следующей итерации event loop через безопасную coroutine. Обычные callers сохраняют немедленный stop.
6. Desired reload groups хранятся отдельно от ready groups. Availability новых/изменённых групп повторно проверяется каждый tick; reconnect hook читает ready registry через callable.
7. Reload обновляет publish-time safety limits shared AI client до создания/использования orchestrator.
8. Important-service scenario text загружается PromptLoader из tracked prompt data file. Initiator запрещает contact, responder обязан содержать contact; для one-turn групп important exchange не выбирается.
9. Cooldown считает responder участником только при наличии persisted `responder_message_id`. Поле добавляется идемпотентно при `init_db`; пропуск exchange реализуется concrete store method.
10. OpenRouter close использует `finally`, чтобы закрыть owned HTTP transport и сохранить исходную SDK exception.

## Risks / Trade-offs

- [Pending group создаёт Telegram checks каждый tick] → проверяются только группы, чья membership signature ещё не ready; ready groups не требуют повторного join.
- [Deferred disconnect создаёт background task] → wrapper поглощает и безопасно логирует stop error без raw Telegram data.
- [Prompt data может быть malformed] → loader валидирует обязательные scenario keys и завершает startup с понятной ошибкой.
- [Marked ID недоступен для primitive target] → сохраняется явный configured fallback как compatibility path.

## Migration Plan

`ExchangeStore.init_db` идемпотентно добавляет nullable `responder_message_id`; существующие записи остаются валидными и не приписывают responder turn без доказательства отправки. После deploy settings с `socks4://` будут отклонены; оператор должен заменить схему на `socks5://` или HTTP(S). Rollback выполняется возвратом merge-коммита.
