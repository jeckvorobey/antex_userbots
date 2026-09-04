## MODIFIED Requirements

### Requirement: Strict OpenRouter requests
The system SHALL send non-streaming Chat Completions through the official async OpenRouter SDK with ordered models and explicit local-test provider preferences.

#### Scenario: Request uses non-ZDR local-test policy
- **WHEN** either generation method calls OpenRouter in the local test runtime
- **THEN** `chat.send_async` receives configured models in order and provider preferences with `zdr=false`, `data_collection="deny"`, `allow_fallbacks=true`, and `require_parameters=true`
