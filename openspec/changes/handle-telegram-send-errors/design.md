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

## Rollback

Изменение откатывается удалением обработки permanent errors и использования persisted drafts. Новая nullable колонка `responder_text` совместима со старым runtime и может остаться в SQLite без влияния на него.
