## MODIFIED Requirements

### Requirement: Gemini reply generation
The system SHALL generate replies by sending system instruction, rendered history, and user message to the configured Gemini model.

#### Scenario: Reply request includes history and message
- **WHEN** `generate_reply` is called with history and a user message
- **THEN** the Gemini request contents include rendered history followed by `Пользователь: <message>`

#### Scenario: Start topic request includes topic
- **WHEN** `start_topic` is called
- **THEN** the Gemini request contents include `Тема разговора: <topic>`

#### Scenario: Start topic adapts intent to group city
- **WHEN** scheduled start-topic generation is composed for a group
- **THEN** the system instruction includes rules to transform the shared topic intent into one natural question for that group's city and not mention another city

#### Scenario: Start topic uses human opening variants
- **WHEN** scheduled start-topic generation is composed
- **THEN** the prompt instructs Gemini to begin like an ordinary chat participant using `привет`, `всем привет`, `здравствуйте`, or by asking the question directly without an introductory word
