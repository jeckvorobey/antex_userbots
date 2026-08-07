## Context

`SwarmOrchestrator` выполняет scheduled exchange в две стадии. Для responder exchange запись остаётся `started` до успешного Telegram `send_message`. Любое исключение отправки прерывает `run_once`; следующий scheduler tick снова выбирает ту же запись через `get_due_started_exchange`.

## Decisions

### Permanent Telegram send errors

К постоянным ограничениям относятся `UserBannedInChannelError`, `ChatWriteForbiddenError`, `ChannelPrivateError`, `UserNotParticipantError`. Они означают, что повтор того же exchange без изменения внешнего состояния не имеет смысла.

При такой ошибке orchestrator:

1. логирует структурированный warning;
2. переводит exchange в `skipped` через существующий `mark_exchange_skipped`;
3. возвращает управление без исключения;
4. не сохраняет сообщение в history как отправленное.

### Temporary and unknown failures

Flood-wait, transport/network failures и неизвестные исключения не маскируются как permanent. Они продолжают пробрасываться, чтобы существующая retry/observability семантика сохранялась.

### Avoid duplicate LLM generation

Текст сохраняется в SQLite до Telegram send:

- `question_text` используется как persisted initiator draft;
- новый nullable `responder_text` используется как persisted responder draft.

На повторном тике orchestrator сначала использует persisted draft и вызывает Gemini только если draft отсутствует.

### Runtime quarantine and replacement

После permanent send error аккаунт выключается из runtime-пула: scheduled turns и addressed-reply router его больше не используют, а supervisor не пытается переподключить остановленный клиент. Quarantine сохраняется в SQLite и применяется до запуска клиентов после рестарта. По текущему продуктовому требованию аккаунт исключается из всего swarm-runtime до ручной проверки и снятия quarantine.

Если в пуле остаётся подходящая третья персона, неотправленный turn переназначается ей сразу. Для responder удаляется его draft, потому что он принадлежит persona отключённого аккаунта. Для initiator удаляется question draft по той же причине. Если замены нет, exchange переводится в `skipped`.

Persisted exchange может ссылаться на аккаунт, который был отключён между сохранением записи и следующим scheduler tick. До попытки занять slot и до вызова LLM orchestrator проверяет доступность назначенного участника. Недоступный участник заменяется тем же механизмом, что и permanent send error; если подходящей замены нет, exchange становится `skipped`. `SwarmManager` также возвращает `acquired = false` для неизвестного или неактивного bot_id вместо `KeyError`.

Permanent error в addressed-reply пути использует то же durable quarantine-хранилище до runtime disable. Каждая запись quarantine сопровождается structured error log с `bot_id`, причиной и `auto_reuse=false`. Telegram user id отключённого аккаунта остаётся в `swarm_user_ids`: оставшиеся handlers продолжают игнорировать поздние или внешние сообщения этого userbot как bot-to-bot traffic. Когда в активном пуле остаётся меньше двух аккаунтов, orchestrator не создаёт новый exchange и завершает tick без исключения.

## Rollback

Изменение откатывается удалением обработки permanent errors и использования persisted drafts. Новая nullable колонка `responder_text` совместима со старым runtime и может остаться в SQLite без влияния на него.
