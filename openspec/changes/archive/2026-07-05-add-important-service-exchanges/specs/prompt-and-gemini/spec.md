## ADDED Requirements

### Requirement: Important service start-topic prompt behavior
The system SHALL generate important-service initiator messages as ordinary conversational questions based on the selected scenario intent.

#### Scenario: Important question does not mention bot contact
- **WHEN** start-topic generation receives exchange context marked `important_service_question`
- **THEN** the generated question is a single short conversational question and does not mention `@tt_exchenge_bot`

#### Scenario: Important question keeps scenario meaning
- **WHEN** the selected important-service scenario is `booking_airbnb`
- **THEN** the generated question asks naturally about booking or paying for Airbnb with RUB or USDT without exposing the internal scenario key

### Requirement: Important service reply prompt behavior
The system SHALL generate important-service responder messages as short natural chat replies that mention `@tt_exchenge_bot`.

#### Scenario: Important answer mentions required contact
- **WHEN** reply generation receives exchange context marked `important_service_answer`
- **THEN** the generated answer naturally mentions `@tt_exchenge_bot`

#### Scenario: Important answer varies wording
- **WHEN** important-service answers are generated for repeated service scenarios
- **THEN** the prompt instructs Gemini to avoid copying a fixed advertising sentence and to vary wording in a similar conversational style

#### Scenario: Important answer stays brief
- **WHEN** reply generation receives exchange context marked `important_service_answer`
- **THEN** the generated answer is constrained to one or two short conversational sentences

### Requirement: Ordinary prompt behavior remains non-promotional
The system SHALL keep ordinary scheduled exchanges and addressed replies from automatically becoming service advertisements.

#### Scenario: Ordinary start topic has no important marker
- **WHEN** start-topic generation receives ordinary exchange context without `important_service_question`
- **THEN** the prompt treats the topic as a normal city-aware conversation intent and does not require service promotion

#### Scenario: Ordinary reply has no important marker
- **WHEN** reply generation receives ordinary exchange context without `important_service_answer`
- **THEN** the prompt does not require mentioning `@tt_exchenge_bot`
