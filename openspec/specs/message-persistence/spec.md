# Message And Exchange Persistence

## Purpose

Define SQLite persistence for chat history and scheduled exchange state.
## Requirements

### Requirement: Shared SQLite database
The system SHALL use one shared `aiosqlite.Connection` and one shared asynchronous write lock for message history and scheduled exchange persistence during a runtime.

#### Scenario: Persistence components share one connection
- **WHEN** runtime initializes message history and exchange storage
- **THEN** both components receive the same open SQLite database dependency and neither component opens or closes its own connection

#### Scenario: Concurrent writes are serialized
- **WHEN** message inserts, exchange inserts, updates, deletes, schema creation, migrations, or index creation run concurrently
- **THEN** each write operation and its commit execute under the same asynchronous lock

#### Scenario: Reads wait for active writes
- **WHEN** a read starts while another coroutine has an unfinished write transaction
- **THEN** the read waits for that transaction to commit or roll back before querying the shared connection

### Requirement: SQLite connection configuration
The system SHALL open the configured database path with a 30-second connection timeout, restrict filesystem database permissions to owner read/write, and enable WAL journal mode, NORMAL synchronous mode, a 30000-millisecond busy timeout, and foreign key enforcement.

#### Scenario: Shared connection is configured
- **WHEN** the shared SQLite database opens
- **THEN** `journal_mode` is `wal`, `synchronous` is `NORMAL`, `busy_timeout` is `30000`, and `foreign_keys` is enabled

#### Scenario: Existing database files are preserved
- **WHEN** the shared SQLite database opens an existing `data/history.db`
- **THEN** it uses the existing database and does not delete the database, WAL, or shared-memory files

#### Scenario: Database file is private
- **WHEN** a filesystem-backed SQLite database opens
- **THEN** runtime restricts the database file permissions to owner read and write (`0600`)

### Requirement: Temporary SQLite lock retry
The system SHALL execute a locked SQLite operation at most five times using delays of 0.2, 0.5, 1, and 2 seconds between attempts while preserving all non-lock errors.

#### Scenario: Temporary database lock is retried
- **WHEN** an operation raises `aiosqlite.OperationalError` containing `database is locked` or `database table is locked`
- **THEN** the system rolls back, logs the next attempt with its delay and operation name, waits, and retries within the five-attempt limit

#### Scenario: Schema initialization survives a temporary lock
- **WHEN** schema initialization encounters a temporary SQLite lock and a later attempt succeeds
- **THEN** initialization completes without terminating the runtime

#### Scenario: Unknown operational error is propagated
- **WHEN** an operation raises any other `aiosqlite.OperationalError`
- **THEN** the error is raised immediately without retry or suppression

#### Scenario: Retry limit is exhausted
- **WHEN** all five attempts fail with a recognized lock error
- **THEN** the final lock error is raised

### Requirement: Message history table
The system SHALL create and migrate a `messages` table and supporting indexes for persisted chat history.

#### Scenario: History initialization creates storage
- **WHEN** `MessageHistory.init_db` runs against a file path
- **THEN** the parent directory is created as needed and the `messages` table exists

#### Scenario: History initialization is idempotent
- **WHEN** `MessageHistory.init_db` runs more than once
- **THEN** initialization succeeds without duplicate-column or duplicate-index failure

#### Scenario: History indexes are created
- **WHEN** `MessageHistory.init_db` runs
- **THEN** indexes exist for user history and chat/bot session history lookups

### Requirement: User history retrieval
The system SHALL persist messages by user id and return limited chronological history.

#### Scenario: User messages are isolated
- **WHEN** messages are saved for different user ids
- **THEN** `get_history(user_id)` returns only that user's messages

#### Scenario: History limit is applied
- **WHEN** more messages exist than the requested limit
- **THEN** only the limited number of most recent messages is returned in chronological order

### Requirement: Session history retrieval
The system SHALL retrieve chat-scoped session history with optional bot and session-start filters using sortable UTC timestamps for range filtering and chronological ordering.

#### Scenario: Chat history includes multiple users
- **WHEN** multiple users have messages in the same chat
- **THEN** `get_session_history(chat_id)` returns messages from those users in chronological order

#### Scenario: Different chats are isolated
- **WHEN** messages exist in different chats
- **THEN** `get_session_history` returns only messages for the requested chat id

#### Scenario: None chat id returns empty list
- **WHEN** `get_session_history` is called with `chat_id = None`
- **THEN** it returns an empty list

#### Scenario: Session start uses an indexed UTC range
- **WHEN** `session_start` is provided
- **THEN** the query compares canonical UTC timestamp strings directly and returns only messages at or after that timestamp ordered by `created_at` and `id`

#### Scenario: Bot id filters session history
- **WHEN** `bot_id` is provided
- **THEN** session history contains only messages saved for that bot id

### Requirement: Swarm metadata persistence
The system SHALL persist swarm metadata with messages.

#### Scenario: Metadata is returned with session history
- **WHEN** a message is saved with `bot_id`, `exchange_id`, `message_origin`, and `reply_to_message_id`
- **THEN** `get_session_history` returns those metadata fields with role and text

### Requirement: Exchange state table
The system SHALL create and migrate a `scheduled_exchanges` table and supporting indexes for group-scoped orchestrator state.

#### Scenario: Exchange store initialization creates storage
- **WHEN** `ExchangeStore.init_db` runs
- **THEN** the `scheduled_exchanges` table exists with fields for group id, group chat id, pair, window, topic, question, due timestamps, message ids, status, and lifecycle timestamps

#### Scenario: Exchange store initialization is idempotent
- **WHEN** `ExchangeStore.init_db` runs with existing columns and indexes
- **THEN** initialization succeeds without duplicate-column or duplicate-index failure

#### Scenario: Exchange indexes are created
- **WHEN** `ExchangeStore.init_db` runs
- **THEN** indexes exist for group window lookup, due responder lookup, and recent anti-repeat queries

### Requirement: Exchange lifecycle state
The system SHALL persist planned, started, and completed scheduled exchange state by group.

#### Scenario: Planned exchange is created
- **WHEN** an exchange is created
- **THEN** it receives a UUID, group id, real group chat id, pair key, topic key, optional window key, optional initiator due timestamp, and status `planned`

#### Scenario: Exchange is marked started
- **WHEN** the initiator message is sent
- **THEN** the exchange stores status `started`, initiator message id, question text, normalized question signature, responder due timestamp, and started timestamp

#### Scenario: Exchange is marked completed
- **WHEN** the responder stage completes or an exchange with one max turn is finished
- **THEN** the exchange status becomes `completed` and completed timestamp is stored

### Requirement: LLM draft переживает повторную попытку Telegram send
Runtime SHALL сохранять сгенерированный текст в SQLite до вызова Telegram `send_message`.

#### Scenario: Вопрос инициатора уже сгенерирован
- **WHEN** planned exchange содержит `question_text`
- **THEN** runtime MUST использовать этот текст для send retry
- **AND** MUST NOT снова вызывать `start_topic`

#### Scenario: Ответ responder уже сгенерирован
- **WHEN** started exchange содержит `responder_text`
- **THEN** runtime MUST использовать этот текст для send retry
- **AND** MUST NOT снова вызывать AI client `generate_reply`

#### Scenario: Отправка успешна
- **WHEN** Telegram подтверждает send
- **THEN** runtime MUST сохранить message history и обновить статус exchange

#### Scenario: Отправка неуспешна
- **WHEN** Telegram send завершается ошибкой
- **THEN** runtime MUST NOT сохранять соответствующее сообщение в history как отправленное

### Requirement: Exchange anti-repeat queries
The system SHALL expose group-scoped persisted queries used by orchestrator anti-repeat behavior while bounding transferred rows by caller limits where possible.

#### Scenario: Recent bot ids follow scheduled message order
- **WHEN** completed and started exchanges exist for multiple groups
- **THEN** recent bot id retrieval for a group returns unique bot ids only from that group in recent scheduled message order

#### Scenario: Recent bot ids are limited in SQL
- **WHEN** more unique scheduled bot ids exist than the requested limit
- **THEN** `get_recent_bot_ids(limit)` returns only the requested count without relying on Python to scan every event row

#### Scenario: Recent topic keys are limited
- **WHEN** more topic keys exist than the requested limit across multiple groups
- **THEN** only keys from the latest started or completed exchanges in the requested group up to the limit are returned

#### Scenario: Recent question signatures are normalized
- **WHEN** question signatures are stored with punctuation or spacing
- **THEN** anti-repeat queries use normalized lowercase signatures without punctuation for the requested group

#### Scenario: Due started exchange is returned
- **WHEN** a started exchange in a group has a responder due timestamp not later than now
- **THEN** `get_due_started_exchange` returns that group exchange record

### Requirement: Scheduled history chat id
The system SHALL save scheduled messages under the real resolved Telegram group chat id.

#### Scenario: Scheduled message uses resolved chat id
- **WHEN** an orchestrator sends scheduled initiator or responder text
- **THEN** message history stores `chat_id` equal to the resolved Telegram group id, not a global fallback

### Requirement: Important service exchange metadata
The system SHALL persist whether a scheduled exchange is ordinary or important-service and SHALL persist the important-service scenario key for important-service exchanges.

#### Scenario: Important service exchange is created
- **WHEN** the orchestrator creates an important-service exchange
- **THEN** `scheduled_exchanges` stores `exchange_kind = important_service` and the selected `important_scenario`

#### Scenario: Ordinary exchange is created
- **WHEN** the orchestrator creates an ordinary scheduled exchange
- **THEN** `scheduled_exchanges` stores or treats the exchange as `exchange_kind = regular` with no important-service scenario

#### Scenario: Legacy rows remain regular
- **WHEN** `ExchangeStore.init_db` migrates an existing database whose `scheduled_exchanges` rows do not have important-service metadata
- **THEN** those rows are treated as ordinary scheduled exchanges

### Requirement: Important service state queries
The system SHALL expose group-scoped persisted queries for important-service cadence and scenario rotation.

#### Scenario: Latest important service exchange is returned by group
- **WHEN** important-service exchanges exist for multiple groups
- **THEN** querying the latest important-service exchange for `danang` returns only `danang` state

#### Scenario: Recent important service date is available
- **WHEN** a group has a started or completed important-service exchange
- **THEN** the store can return the latest important-service timestamp used for UTC calendar-day cadence checks

#### Scenario: Latest scenario drives rotation
- **WHEN** a group has a latest important-service exchange with scenario `booking_airbnb`
- **THEN** the store can return `booking_airbnb` so the orchestrator can select `exchange_usdt`

### Requirement: Important service indexes
The system SHALL create idempotent indexes that support group-scoped latest important-service exchange lookup.

#### Scenario: Important service indexes are created
- **WHEN** `ExchangeStore.init_db` runs
- **THEN** indexes for group, chat, exchange kind, important scenario, and recent lifecycle timestamp lookup exist without duplicate-index failure

### Requirement: Exchange activity sort key
The system SHALL persist a `last_activity_at` timestamp on scheduled exchanges for recent and latest exchange lookups.

#### Scenario: New exchange stores activity timestamp
- **WHEN** `ExchangeStore.create_exchange` creates a planned exchange
- **THEN** the exchange has a non-empty `last_activity_at`

#### Scenario: Started exchange updates activity timestamp
- **WHEN** `ExchangeStore.mark_exchange_started` marks an exchange as started
- **THEN** `last_activity_at` equals the stored `started_at` value

#### Scenario: Completed exchange updates activity timestamp
- **WHEN** `ExchangeStore.mark_exchange_completed` marks an exchange as completed
- **THEN** `last_activity_at` equals the stored `completed_at` value

#### Scenario: Legacy exchange rows are backfilled
- **WHEN** `ExchangeStore.init_db` migrates a legacy `scheduled_exchanges` table with lifecycle timestamps but no `last_activity_at`
- **THEN** `last_activity_at` is filled from `completed_at`, `started_at`, or `created_at` in that priority order

### Requirement: Index-friendly exchange hot-path lookups
The system SHALL use persisted UTC timestamp strings and `last_activity_at` ordering for due, recent, and latest scheduled exchange queries.

#### Scenario: Due responder compares stored timestamps directly
- **WHEN** `get_due_started_exchange` checks due responder rows
- **THEN** it compares `responder_scheduled_at` to the serialized current UTC timestamp without wrapping the column in a SQL timestamp function

#### Scenario: Recent question context follows activity order
- **WHEN** recent scheduled questions are requested for a group
- **THEN** the returned rows are ordered by `last_activity_at` descending

#### Scenario: Latest important service exchange follows activity order
- **WHEN** latest important-service exchange state is requested for a group
- **THEN** the returned row is selected by `last_activity_at` descending

### Requirement: Activity indexes
The system SHALL create idempotent indexes that support group-scoped and chat-scoped recent exchange activity lookups.

#### Scenario: Activity indexes are created
- **WHEN** `ExchangeStore.init_db` runs
- **THEN** indexes for group/chat status and `last_activity_at` lookup exist without duplicate-index failure

### Requirement: History retention cleanup
The system SHALL support deleting persisted message and scheduled exchange rows older than the configured retention window.

#### Scenario: Old history is pruned at runtime bootstrap
- **WHEN** runtime initializes persistence with a positive retention window
- **THEN** messages and scheduled exchanges older than the cutoff are deleted before normal operation continues

#### Scenario: Non-positive retention disables pruning
- **WHEN** the configured retention window is zero or negative
- **THEN** automatic history pruning is skipped
