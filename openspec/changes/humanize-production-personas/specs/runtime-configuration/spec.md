## ADDED Requirements

### Requirement: Google Search grounding settings
The system SHALL expose strict non-secret Gemini settings for enabling reply grounding and limiting published sources.

#### Scenario: Generic grounding default is safe
- **WHEN** `[gemini]` omits Google Search grounding fields
- **THEN** grounding is disabled by default and the maximum source count uses a bounded code default

#### Scenario: Production enables grounding
- **WHEN** production settings are loaded for this instance
- **THEN** `google_search_grounding_enabled` is true for the shared Gemini client used by all bots

#### Scenario: Source limit is bounded
- **WHEN** `google_search_max_sources` is configured
- **THEN** settings validation accepts only an integer within the supported bounded range

#### Scenario: Unknown grounding field is rejected
- **WHEN** `[gemini]` contains an unsupported or misspelled grounding setting
- **THEN** strict TOML validation fails
