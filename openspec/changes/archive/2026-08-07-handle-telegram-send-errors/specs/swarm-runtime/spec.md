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
- **THEN** runtime MUST не запускать этот аккаунт после рестарта
- **AND** аккаунт MUST оставаться исключённым из всех automated swarm flows до ручной проверки и снятия quarantine

#### Scenario: Нет персоны для замены

- **WHEN** permanent send error получен и после отключения аккаунта остаётся меньше двух подходящих участников
- **THEN** exchange MUST получить статус `skipped`
- **AND** skipped exchange MUST не выбираться `get_due_started_exchange`
- **AND** scheduler tick MUST завершиться без исключения

#### Scenario: Persisted exchange с недоступным участником

- **WHEN** due planned или started exchange ссылается на bot_id, которого нет в активном runtime-пуле или среди доступных persona-профилей
- **THEN** runtime MUST NOT занимать его scheduled slot и MUST NOT вызывать LLM от его имени
- **AND** MUST переназначить неотправленный turn на другую подходящую персону
- **OR**, если замены нет, пометить exchange `skipped` с явной причиной
- **AND** scheduler tick MUST завершиться без `KeyError`

#### Scenario: Ошибка временная или неизвестная

- **WHEN** Telegram send завершается FloodWait, transport timeout, connection error или неизвестной RPC ошибкой
- **THEN** runtime MUST не отключать аккаунт и не переводить exchange в `skipped`
- **AND** исключение MUST оставаться видимым для retry/observability

#### Scenario: Permanent ошибка при addressed reply

- **WHEN** `event.reply` завершается permanent Telegram send error
- **THEN** runtime MUST сохранить durable quarantine для bot_id до его отключения
- **AND** MUST записать structured log с bot_id, причиной и `auto_reuse=false`
- **AND** MUST NOT сохранить неотправленный assistant reply в history

#### Scenario: Активный пул уменьшился

- **WHEN** после quarantine в active pool остаётся меньше двух ботов
- **THEN** runtime MUST не создавать новый scheduled exchange
- **AND** scheduler tick MUST завершиться без исключения

#### Scenario: Позднее сообщение отключённого аккаунта

- **WHEN** отключённый swarm-аккаунт отправляет сообщение после runtime disable
- **THEN** его Telegram user id MUST оставаться в swarm sender set
- **AND** активные reply routers MUST игнорировать его как bot-to-bot traffic
