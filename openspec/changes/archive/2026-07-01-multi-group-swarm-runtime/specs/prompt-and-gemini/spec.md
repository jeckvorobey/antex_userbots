## MODIFIED Requirements

### Requirement: Prompt composition
The system SHALL compose generated-task prompts from base prompt, bot persona, and optional exchange context including scheduled group context.

#### Scenario: Base prompt and persona are combined
- **WHEN** a base prompt and persona are available
- **THEN** the composed prompt contains the stripped base prompt followed by stripped persona separated by a blank line

#### Scenario: Exchange context is appended
- **WHEN** exchange context is provided
- **THEN** it is appended after base prompt and persona separated by a blank line

#### Scenario: Scheduled group context is appended
- **WHEN** scheduled exchange composition receives group city or group id context
- **THEN** that context is included in the exchange context passed to prompt composition

#### Scenario: Missing persona file is allowed
- **WHEN** the configured persona file does not exist
- **THEN** prompt composition logs a warning and continues without persona text

#### Scenario: Unsafe persona path is rejected
- **WHEN** `persona_file` is absolute or contains `..`
- **THEN** prompt composition raises `ValueError`
