## MODIFIED Requirements

### Requirement: Ignore non-addressed messages
The system SHALL ignore incoming events that are outside enabled configured groups or are not addressed replies to the current bot, and SHALL reject non-reply events before resolving the Telegram sender entity.

#### Scenario: Unknown group is ignored
- **WHEN** an incoming event chat id is not one of the enabled configured groups
- **THEN** the addressed reply router returns `false` and sends no response

#### Scenario: Empty allowlist rejects every group
- **WHEN** no enabled configured group has been resolved to a numeric chat id
- **THEN** the addressed reply router rejects every incoming event instead of disabling group filtering

#### Scenario: Target-only group is resolved before handler registration
- **WHEN** an enabled group is configured only with `group_target`
- **THEN** runtime resolves its numeric chat id and adds that id to the shared allowlist before registering addressed-reply handlers

#### Scenario: Disabled group is ignored
- **WHEN** an incoming event chat id belongs to a configured but disabled group
- **THEN** the addressed reply router returns `false` and sends no response

#### Scenario: Non-reply message is ignored without sender lookup
- **WHEN** an incoming event is not a Telegram reply
- **THEN** the addressed reply router returns `false`, sends no response, and does not resolve the sender entity

#### Scenario: Reply to another bot is ignored
- **WHEN** the replied-to message sender id differs from the current bot Telegram user id
- **THEN** the addressed reply router returns `false` and sends no response

#### Scenario: Missing reply message is ignored
- **WHEN** an event is marked as reply but the replied-to message cannot be loaded
- **THEN** the addressed reply router returns `false`

### Requirement: Answer addressed human reply
The system SHALL answer a human reply only when the reply targets the current bot inside an enabled configured group, and SHALL make the answer eligible for publication exactly four minutes after the event is accepted.

#### Scenario: Addressed reply uses absolute publication deadline
- **WHEN** a non-bot human sender replies in an enabled configured group to a message sent by the current bot
- **THEN** the router records a deadline 240 seconds after acceptance, processes the reply, waits only until that deadline if necessary, replies in Telegram, and returns `true`

#### Scenario: Human slot wait does not add another full delay
- **WHEN** an accepted reply waits for an earlier human reply to release the same bot slot
- **THEN** processing uses the original deadline and does not start a new 240-second interval after acquiring the slot

#### Scenario: Local fallback uses the same deadline
- **WHEN** external reply LLM usage is disabled or generated output is unsafe
- **THEN** the router publishes the safe local fallback no earlier than the accepted event deadline

### Requirement: Addressed reply abuse throttling
The system SHALL rate-limit addressed human replies before any external LLM call, bound pending replies per bot, and remove expired in-memory rate-limit state.

#### Scenario: Burst sender is throttled
- **WHEN** the same sender exceeds the configured addressed-reply limit for the same bot in the same chat inside the configured time window
- **THEN** the router returns `false`, sends no Telegram response, and skips the Gemini request

#### Scenario: Sender under the limit is processed
- **WHEN** the sender stays within the configured addressed-reply rate limit
- **THEN** the router continues normal addressed reply processing

#### Scenario: Pending reply capacity is exhausted
- **WHEN** the current bot already has the configured maximum number of accepted unfinished addressed replies
- **THEN** the router returns `false` and skips history, prompt, Gemini, delay, and Telegram reply work for the new event

#### Scenario: Pending capacity is released
- **WHEN** accepted reply processing succeeds, fails, or is cancelled
- **THEN** the router releases that pending slot

#### Scenario: Expired sender state is removed
- **WHEN** all timestamps for a rate-limit key are older than the active window during periodic cleanup
- **THEN** both the timestamps and their chat/sender/bot key are removed from memory
