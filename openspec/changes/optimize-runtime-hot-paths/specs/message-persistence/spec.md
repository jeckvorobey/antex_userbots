## MODIFIED Requirements

### Requirement: SQLite connection configuration
The system SHALL open the configured database path with a 30-second connection timeout, restrict filesystem database permissions to owner read/write, and enable WAL journal mode, NORMAL synchronous mode, a 30000-millisecond busy timeout, and foreign key enforcement.

#### Scenario: Database file is private
- **WHEN** a filesystem-backed SQLite database opens
- **THEN** runtime restricts the database file permissions to owner read and write (`0600`)

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
