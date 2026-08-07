## MODIFIED Requirements

### Requirement: Scheduled exchange устойчив к Telegram send restrictions

Swarm runtime MUST не завершать scheduler tick исключением при permanent Telegram send error: `UserBannedInChannelError`, `ChatWriteForbiddenError`, `ChannelPrivateError` или `UserNotParticipantError`.

#### Scenario: У ответчика нет права писать в целевой чат

- **WHEN** responder `send_message` возвращает permanent Telegram send error
- **THEN** runtime отключает этот аккаунт от scheduled и addressed-reply обработки
- **AND** освобождает занятый scheduled slot
- **AND** не сохраняет responder message в history как отправленное
- **AND** переносит turn на другую доступную персону, отличную от initiator
- **OR**, если замены нет, помечает exchange `skipped`

#### Scenario: Runtime перезапущен после permanent ошибки

- **WHEN** аккаунт ранее получил permanent Telegram send error в целевой группе
- **THEN** runtime MUST не запускать этот аккаунт для той же группы после рестарта
- **AND** аккаунт MUST оставаться доступным для других групп только после отдельной проверки их состояния

#### Scenario: Нет персоны для замены

- **WHEN** permanent send error получен и после отключения аккаунта остаётся меньше двух подходящих участников
- **THEN** exchange MUST получить статус `skipped`
- **AND** skipped exchange MUST не выбираться `get_due_started_exchange`
- **AND** scheduler tick MUST завершиться без исключения

#### Scenario: Ошибка временная или неизвестная

- **WHEN** Telegram send завершается FloodWait, transport timeout, connection error или неизвестной RPC ошибкой
- **THEN** runtime MUST не отключать аккаунт и не переводить exchange в `skipped`
- **AND** исключение MUST оставаться видимым для retry/observability
