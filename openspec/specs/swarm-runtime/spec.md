# Swarm Runtime

## Purpose

Define how enabled Telegram userbot accounts are started, supervised, registered for routing, and connected to the target group.
## Requirements
### Requirement: Runtime context initialization
The system SHALL initialize one shared SQLite connection and one shared provider-neutral AI client before starting swarm clients, and SHALL close both exactly once during shutdown.

#### Scenario: Runtime dependencies are created
- **WHEN** the application starts with valid settings
- **THEN** SQLite stores, prompt loading, OpenRouter free-model diagnostics, topic selection, prompt composition, and one shared OpenRouter-backed `ai_client` are initialized before bot clients

#### Scenario: OpenRouter free-model diagnostics are written
- **WHEN** runtime context is built with a valid OpenRouter key
- **THEN** the system queries OpenRouter's models catalog for free text-output models, checks configured `[openrouter].models` with short `1` probe requests, writes `logs/openrouter_free_models.json` with model connection slugs sorted best-first and per-configured-model availability, and does not replace the configured `[openrouter].models` list

#### Scenario: Runtime dependencies close once
- **WHEN** runtime shuts down
- **THEN** the AI client and shared SQLite connection each close exactly once

#### Scenario: Partial initialization cleans up resources
- **WHEN** context construction fails after SQLite or the AI client is created
- **THEN** every successfully created owned resource is closed before the error propagates

#### Scenario: Shared proxy reaches both transports
- **WHEN** settings provide `PROXY`
- **THEN** runtime passes the same value to every Telethon client and the OpenRouter AI client

#### Scenario: Direct transports omit proxy
- **WHEN** settings do not provide `PROXY`
- **THEN** runtime constructs Telethon and OpenRouter without proxy configuration

### Requirement: Graceful operator shutdown
The system SHALL treat an operator interrupt at the process entry point as a successful graceful shutdown after asynchronous runtime cleanup completes.

#### Scenario: Ctrl+C stops without traceback
- **WHEN** the operator sends an interrupt while the swarm is running
- **THEN** supervisor tasks are cancelled, owned runtime resources are closed, and the process exits without printing a `CancelledError` or `KeyboardInterrupt` traceback

#### Scenario: Runtime failures remain visible
- **WHEN** the application exits because of an exception other than an operator interrupt
- **THEN** the exception propagates from the process entry point

### Requirement: Enabled bot startup
The system SHALL start only enabled swarm bot profiles, collect their Telegram user ids, and clean up any client that fails before active-pool registration completes.

#### Scenario: Disabled bot is skipped
- **WHEN** a bot profile has `enabled = false`
- **THEN** the swarm manager does not start a client for that bot

#### Scenario: Started bot becomes active
- **WHEN** an enabled bot starts successfully and returns a Telegram user id
- **THEN** its bot id is added to the active pool and its Telegram user id is added to `swarm_user_ids`

#### Scenario: Startup failure excludes and stops bot
- **WHEN** an enabled bot fails after its Telegram client was created or connected
- **THEN** the client is stopped and removed, the runtime state is marked as error, and the bot is not added to the active pool

### Requirement: Global account messaging eligibility at startup
Before a swarm account is registered as active, the system SHALL perform a non-publishing global messaging API health-check. A confirmed deactivated, revoked, or globally banned account SHALL be disabled, stopped, persistently quarantined, and logged as requiring attention; group-level failures SHALL remain non-global.

#### Scenario: Global messaging check succeeds
- **WHEN** an enabled bot starts and Telegram accepts the non-publishing messaging action
- **THEN** membership checks and normal active-pool registration continue

#### Scenario: Account is globally unavailable
- **WHEN** Telegram returns a confirmed deactivated, revoked, or globally banned account error during connection or the startup messaging check
- **THEN** the client is stopped, the bot is not added to the active pool, global quarantine is saved, and an error log identifies the bot as requiring attention

#### Scenario: Frozen messaging method is rejected
- **WHEN** Telegram returns `FROZEN_METHOD_INVALID` during the non-publishing messaging action
- **THEN** the runtime treats the account as globally unavailable and applies global quarantine

#### Scenario: Global quarantine persistence fails
- **WHEN** the runtime cannot persist global quarantine for a confirmed globally unavailable account
- **THEN** the account remains disabled in memory and startup fails instead of continuing without durable quarantine

#### Scenario: Recipient-specific restriction is not global quarantine
- **WHEN** a group cannot be resolved or does not confirm `can_write=True`
- **THEN** startup rejects that bot without classifying the condition or persisting it as a global account freeze

### Requirement: Minimum active bot count
The system SHALL require at least two enabled bots before startup and at least two active bots after startup.

#### Scenario: Fewer than two enabled bots
- **WHEN** swarm mode is started with fewer than two enabled bot profiles, including after applying persisted quarantine
- **THEN** startup fails

#### Scenario: Fewer than two active bots after startup
- **WHEN** startup leaves fewer than two active bots
- **THEN** the orchestrator job is not registered and startup fails

### Requirement: Fresh availability determines startup pool
The system SHALL replace only the transient startup availability snapshot before checking enabled bot profiles, preserve durable quarantine rows, and admit a profile only after the global Telegram eligibility check and `can_write=True` for every enabled group. When building the startup pool, durable quarantine SHALL be limited to the bot IDs present in the current enabled profile configuration, matched as exact strings.

#### Scenario: Startup ignores quarantine rows for retired profiles
- **WHEN** durable quarantine contains an account ID that is absent from the current TOML bot profiles
- **THEN** startup SHALL leave that row in SQLite but SHALL NOT exclude any current profile because of it

#### Scenario: Startup filters numeric IDs exactly
- **WHEN** durable quarantine contains configured bot IDs represented by numeric strings of different lengths
- **THEN** startup SHALL exclude each exact matching configured ID and SHALL not coerce, truncate, or merge the values

### Requirement: Handler registration per active bot
The system SHALL register an addressed-reply handler for each active bot client.

#### Scenario: Active bot gets handler
- **WHEN** Telethon events are available and a bot is active
- **THEN** a `NewMessage` handler is registered for that bot client

#### Scenario: Missing active profile is skipped
- **WHEN** an active bot id has no matching enabled profile
- **THEN** handler registration skips that bot id

### Requirement: Target group membership
The system SHALL wait a random inclusive 30–60 second delay before each bot's startup membership check, build one reusable dialog index for that bot, resolve or join every enabled configured group during startup, validate new or changed enabled groups for every active bot after reload before activation, and resolve groups during scheduler ticks only through a currently active bot client.

#### Scenario: Startup membership delay stays within the configured range
- **WHEN** an enabled bot reaches either startup membership hook
- **THEN** the runtime waits a random delay from 30 through 60 seconds before the first membership operation

#### Scenario: Multi-group membership reuses one dialog scan
- **WHEN** one bot checks membership for multiple enabled groups during startup
- **THEN** the runtime scans that bot's available dialogs once and reuses the resulting index for every group check

#### Scenario: Unresolved enabled group rejects startup
- **WHEN** an enabled group cannot be resolved or joined for a bot
- **THEN** that bot does not enter the active pool

#### Scenario: Group write permission is required
- **WHEN** group permission lookup returns false or unknown for a bot
- **THEN** the group check fails without creating global account quarantine

#### Scenario: Reloaded group is checked before activation
- **WHEN** reload adds, enables, or changes the identity of an enabled group
- **THEN** every active bot resolves or joins it and confirms `can_write=True` before routing or scheduling activates the group

#### Scenario: Reloaded group check fails
- **WHEN** any active bot cannot resolve, join, or write to a new or changed enabled group
- **THEN** that group remains excluded from routing and scheduling without globally quarantining the bot

#### Scenario: Scheduler resolves through an active client
- **WHEN** the client originally used during startup has been disabled and another bot remains active
- **THEN** the next scheduler tick resolves configured groups through the remaining active bot client

#### Scenario: Scheduler has no active client
- **WHEN** no bot is active when a scheduler tick starts
- **THEN** the tick returns without resolving a group or raising an exception

#### Scenario: Telegram peer namespaces remain isolated
- **WHEN** a user dialog and a channel dialog expose the same raw entity id
- **THEN** group lookup resolves the namespace-aware channel dialog and never returns the user entity

#### Scenario: Positive basic group id resolves to chat namespace
- **WHEN** a configured positive raw id exists in basic-chat, channel, and user namespaces
- **THEN** group lookup checks the basic-chat marked peer before the channel fallback and never returns the user entity

#### Scenario: Already joined target is reused
- **WHEN** the bot already has a matching dialog by chat id or public target for an enabled group
- **THEN** no join request is sent for that group

#### Scenario: Public target can be joined
- **WHEN** the bot is not already in a public target group
- **THEN** the runtime joins the group using the normalized public target and records the resolved entity in the reusable index

#### Scenario: Join update without entity triggers dialog refresh
- **WHEN** Telegram reports a successful group join through an update container without a chat entity
- **THEN** the runtime refreshes joined dialogs and caches the actual group entity instead of the update container

#### Scenario: Private invite link can be joined without chat id
- **WHEN** `group_target` is a private invite link and no `group_chat_id` is required for membership verification
- **THEN** the runtime imports the invite link and records the resolved entity in the reusable index

#### Scenario: Private invite link with unavailable chat id fails clearly
- **WHEN** `group_chat_id` is configured, the bot cannot see that group, and `group_target` is a private invite link
- **THEN** startup raises a clear membership error instead of importing the invite link

### Requirement: Per-group target cache
The system SHALL cache resolved Telegram group entities independently by normalized group identity for each client.

#### Scenario: Different groups retain independent cached entities
- **WHEN** the runtime resolves two different configured groups for the same client
- **THEN** resolving either group again returns its own cached entity without another dialog scan

#### Scenario: Changed target does not reuse stale entity
- **WHEN** a settings reload changes the chat id or public target used for a group
- **THEN** the runtime resolves the new identity instead of returning the entity cached for the previous identity

### Requirement: Group runtime registry
The system SHALL maintain runtime state for configured groups separately from immutable configuration and SHALL never synthesize an active legacy group when the current configuration explicitly contains only disabled groups.

#### Scenario: Enabled group becomes active after resolve
- **WHEN** at least one active bot resolves an enabled group to a Telegram target and chat id
- **THEN** the group runtime state is available for routing and scheduled exchanges

#### Scenario: Disabled group stops runtime work
- **WHEN** a reload marks a group disabled
- **THEN** routing and scheduling skip that group without stopping the bot pool

#### Scenario: Every configured group is disabled
- **WHEN** the current configuration contains one or more groups and none of them is enabled
- **THEN** runtime returns no active groups and does not create a legacy fallback from compatibility fields

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

### Requirement: Scheduler tick cadence
The system SHALL use 60 seconds as the default orchestrator scheduler tick interval and SHALL allow an explicit TOML value to override that default.

#### Scenario: Default scheduler interval
- **WHEN** configuration does not specify `swarm.orchestrator.tick_seconds`
- **THEN** the scheduler registers the orchestrator job with a 60-second interval

#### Scenario: Explicit scheduler interval
- **WHEN** configuration specifies a valid `swarm.orchestrator.tick_seconds`
- **THEN** the scheduler registers the orchestrator job with that configured interval

### Requirement: Fair sequential group ticks
The system SHALL rotate the first processed group across scheduler ticks while keeping group execution sequential.

#### Scenario: Consecutive ticks rotate the starting group
- **WHEN** multiple enabled groups remain configured across consecutive scheduler ticks
- **THEN** each tick starts with the next group in cyclic configuration order

#### Scenario: Group execution remains sequential
- **WHEN** one scheduler tick processes multiple groups
- **THEN** the next group does not start `run_once` until the previous group finishes

#### Scenario: Reloaded groups reset safely
- **WHEN** settings reload changes the enabled group list
- **THEN** the next start index is normalized to the new list length without skipping or indexing outside the list

### Requirement: Client supervision
The system SHALL keep active bot clients supervised and continue reconnect attempts after unexpected disconnects, client errors, or transient replacement-client startup failures.

#### Scenario: Client error triggers reconnect
- **WHEN** `run_until_disconnected` raises an error
- **THEN** the manager records reconnect state, waits according to backoff, stops the old client when present, and starts the bot again

#### Scenario: Transient replacement startup failure is retried
- **WHEN** a reconnect replacement client fails to start or complete its health checks
- **THEN** the failed replacement is cleaned up and a later supervisor attempt creates another replacement without `KeyError`

#### Scenario: Reconnect discovers globally unavailable account
- **WHEN** the global messaging health-check fails during reconnect
- **THEN** the runtime persistently quarantines and disables the account, removes it from the active pool, and does not schedule another reconnect

#### Scenario: Reconnect checks account before reuse
- **WHEN** a disconnected active bot is reconnecting
- **THEN** it is removed from the active pool before the new client is exposed to the startup health-check and membership hook

### Requirement: Human work has priority
The system SHALL prioritize human reply processing over scheduled tasks for the same bot.

#### Scenario: Human slot blocks scheduled slot
- **WHEN** a human reply owns or is waiting for a bot slot
- **THEN** a scheduled task for that bot receives `acquired = false`

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

### Requirement: Private targets are redacted in logs
The system SHALL not log private Telegram invite hashes.

#### Scenario: Invite link resolve is skipped with redacted log
- **WHEN** group resolution receives a private invite link
- **THEN** direct `get_entity` is skipped and logs contain a redacted marker instead of the invite hash

#### Scenario: Private invite is used as quarantine key
- **WHEN** private invite link является fallback-ключом quarantine
- **THEN** audit-log quarantine содержит redacted marker вместо invite hash

### Requirement: Installed runtime includes storage package
The system SHALL include the entrypoint, `storage` Python package, and tracked runtime prompt/persona assets in built wheel and source distributions, and default asset paths SHALL resolve outside the source checkout.

#### Scenario: Wheel import succeeds
- **WHEN** the project wheel is installed outside the source checkout
- **THEN** runtime modules importing `storage.sqlite_database` load without `ModuleNotFoundError`

#### Scenario: Installed runtime loads default prompts
- **WHEN** the wheel is installed and started from a directory outside the source checkout
- **THEN** default prompt, topic, persona, and important-service resources resolve from installed package data

### Requirement: Startup activation rollback
The system SHALL remove and stop a newly activated bot when persistence of its successful startup availability fails.

#### Scenario: Success snapshot write fails
- **WHEN** a bot completes Telegram startup but its available snapshot cannot be stored
- **THEN** the bot is removed from the active pool, its client is stopped, and startup does not retain contradictory active state

### Requirement: Durable global quarantine ordering
The system SHALL persist global quarantine before updating the transient unavailable snapshot and SHALL keep the account disabled in memory regardless of persistence errors.

#### Scenario: Transient snapshot fails for globally unavailable account
- **WHEN** Telegram confirms global messaging unavailability and snapshot persistence fails
- **THEN** durable quarantine has already been attempted before the snapshot error propagates

### Requirement: Reload group readiness retries
The system SHALL retain configured but temporarily unavailable enabled groups as pending and retry their availability checks on later scheduler ticks.

#### Scenario: Pending group recovers
- **WHEN** a newly configured group fails one transient availability check and succeeds later without another file change
- **THEN** a later tick activates it for routing and scheduling

### Requirement: Reconnect validates current groups
The system SHALL validate a replacement client against the current ready group registry rather than the startup-era group snapshot.

#### Scenario: Group changes before reconnect
- **WHEN** reload activates or retargets a group and a bot reconnects afterward
- **THEN** the replacement client completes membership and write checks for that current group before re-entering the active pool

### Requirement: Private invite classification is case insensitive
The system SHALL classify Telegram private invite URLs without depending on scheme or host letter case and SHALL never log their invite hash.

#### Scenario: Uppercase invite URL
- **WHEN** target is `HTTPS://T.ME/+secret_hash`
- **THEN** runtime uses the private-invite flow and logs only a redacted marker
