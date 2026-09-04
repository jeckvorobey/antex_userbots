## MODIFIED Requirements

### Requirement: Important service reply prompt behavior
The system SHALL generate important-service responder messages as short natural chat replies that mention `https://t.me/tt_exchenge_bot/antex`, including when external generation is disabled or rejected by output safety validation.

#### Scenario: Important answer mentions required miniapp link
- **WHEN** reply generation receives exchange context marked `important_service_answer`
- **THEN** the generated answer naturally mentions `https://t.me/tt_exchenge_bot/antex`

#### Scenario: Important answer varies wording
- **WHEN** important-service answers are generated for repeated service scenarios
- **THEN** the prompt instructs AI client to avoid copying a fixed advertising sentence and to vary wording in a similar conversational style

#### Scenario: Important answer stays brief
- **WHEN** reply generation receives exchange context marked `important_service_answer`
- **THEN** the generated answer is constrained to one or two short conversational sentences

#### Scenario: Important answer uses a safe local fallback
- **WHEN** scheduled LLM use is disabled or an important-service responder output fails safety validation
- **THEN** runtime uses a short local fallback containing the exact approved URL `https://t.me/tt_exchenge_bot/antex`
