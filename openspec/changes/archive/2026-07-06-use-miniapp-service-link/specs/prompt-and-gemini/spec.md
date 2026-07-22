## MODIFIED Requirements

### Requirement: Important service reply prompt behavior
The system SHALL generate important-service responder messages as short natural chat replies that mention `https://t.me/tt_exchenge_bot/antex`.

#### Scenario: Important answer mentions required miniapp link
- **WHEN** reply generation receives exchange context marked `important_service_answer`
- **THEN** the generated answer naturally mentions `https://t.me/tt_exchenge_bot/antex`

#### Scenario: Important answer varies wording
- **WHEN** important-service answers are generated for repeated service scenarios
- **THEN** the prompt instructs Gemini to avoid copying a fixed advertising sentence and to vary wording in a similar conversational style

#### Scenario: Important answer stays brief
- **WHEN** reply generation receives exchange context marked `important_service_answer`
- **THEN** the generated answer is constrained to one or two short conversational sentences

### Requirement: Ordinary prompt behavior remains non-promotional
The system SHALL keep ordinary scheduled exchanges and addressed replies from automatically becoming service advertisements.

#### Scenario: Ordinary reply has no important marker
- **WHEN** reply generation receives ordinary exchange context without `important_service_answer`
- **THEN** the prompt does not require mentioning `https://t.me/tt_exchenge_bot/antex`
