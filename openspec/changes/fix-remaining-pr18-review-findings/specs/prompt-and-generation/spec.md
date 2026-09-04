## ADDED Requirements

### Requirement: Important service scenarios are file-backed
The system SHALL load important-service question and answer intent text from tracked prompt files through `PromptLoader` rather than embedding model instructions in Python.

#### Scenario: Scenario prompt is composed
- **WHEN** an important-service exchange is selected
- **THEN** its question and answer intent comes from the cached tracked prompt resource

### Requirement: OpenRouter owned transport always closes
The system SHALL attempt to close its owned HTTP transport even when OpenRouter SDK shutdown raises.

#### Scenario: SDK exit fails
- **WHEN** the SDK `__aexit__` raises during adapter shutdown
- **THEN** HTTPX `aclose` is awaited and the original SDK exception propagates
