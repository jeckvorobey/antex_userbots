## MODIFIED Requirements

### Requirement: Answer addressed human reply
The system SHALL answer a human reply only when the reply targets the current bot inside an enabled configured group, and SHALL delay publication of that answer by exactly four minutes.

#### Scenario: Addressed reply is processed after fixed delay
- **WHEN** a non-bot human sender replies in an enabled configured group to a message sent by the current bot
- **THEN** the router loads session history for the chat and bot, composes the `reply` prompt with that bot persona, asks Gemini for a response, waits exactly 240 seconds, replies in Telegram, and returns `true`

#### Scenario: Local fallback is delayed
- **WHEN** an addressed reply is processed while external reply LLM usage is disabled or generated output is unsafe
- **THEN** the router selects the safe local fallback response, waits exactly 240 seconds, and replies in Telegram with that fallback
