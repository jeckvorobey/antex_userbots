## MODIFIED Requirements

### Requirement: Group orchestrator reuse
The system SHALL reuse per-group scheduled orchestrators across scheduler ticks while the group's effective runtime signature, including its scheduled LLM security gate, is unchanged.

#### Scenario: Unchanged group reuses orchestrator
- **WHEN** two scheduler ticks run for the same enabled group without settings or resolved target changes
- **THEN** the second tick reuses the existing `SwarmOrchestrator` instance for that group

#### Scenario: Changed group rebuilds orchestrator
- **WHEN** a group's effective schedule, target, city, max turns, skip-human-activity setting, or scheduled LLM gate changes
- **THEN** the next scheduler tick creates a replacement `SwarmOrchestrator` for that group

#### Scenario: Disabled group cache is pruned
- **WHEN** a reload removes or disables a group
- **THEN** the scheduler cache removes that group's orchestrator and stops ticking it

### Requirement: Scheduled exchange устойчив к Telegram send restrictions
Swarm runtime SHALL не завершать scheduler tick исключением при permanent Telegram send error: `UserBannedInChannelError`, `ChatWriteForbiddenError`, `ChannelPrivateError` или `UserNotParticipantError`, кроме отдельной observability-ветки, где durable quarantine не удалось сохранить после обязательного runtime-disable аккаунта.

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

#### Scenario: Quarantine запись addressed reply не сохранилась
- **WHEN** запись durable quarantine после permanent addressed-reply error завершается ошибкой
- **THEN** runtime MUST всё равно отключить bot до распространения ошибки persistence

#### Scenario: Quarantine запись scheduled exchange не сохранилась
- **WHEN** запись durable quarantine после permanent scheduled send error завершается ошибкой
- **THEN** runtime MUST всё равно отключить bot от всех runtime flows до распространения ошибки persistence

#### Scenario: Активный пул уменьшился
- **WHEN** после quarantine в active pool остаётся меньше двух ботов
- **THEN** runtime MUST не создавать новый scheduled exchange
- **AND** scheduler tick MUST завершиться без исключения

#### Scenario: Позднее сообщение отключённого аккаунта
- **WHEN** отключённый swarm-аккаунт отправляет сообщение после runtime disable
- **THEN** его Telegram user id MUST оставаться в swarm sender set
- **AND** активные reply routers MUST игнорировать его как bot-to-bot traffic
