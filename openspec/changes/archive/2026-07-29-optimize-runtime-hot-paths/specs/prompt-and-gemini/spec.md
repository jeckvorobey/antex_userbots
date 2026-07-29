## MODIFIED Requirements

### Requirement: Runtime prompt files
The system SHALL load prompt text from tracked production `.md` files through a non-blocking file cache rather than hardcoding prompt content or blocking the event loop for repeated reads.

#### Scenario: Prompt file is loaded by name
- **WHEN** `PromptLoader.load("system")` is called
- **THEN** it returns the full contents of `system.md` from the configured prompts directory

#### Scenario: Unchanged prompt uses cached text
- **WHEN** the same prompt file is loaded again without a file signature change
- **THEN** the cached text is returned without reading the file contents again

#### Scenario: Changed prompt is refreshed
- **WHEN** a cached prompt file changes its modification timestamp or size
- **THEN** the next load reads and caches the new contents

#### Scenario: File IO stays outside the event loop
- **WHEN** prompt or persona metadata and contents are read
- **THEN** blocking filesystem operations execute outside the asyncio event loop

#### Scenario: Missing prompt fails clearly
- **WHEN** the requested prompt file does not exist
- **THEN** `PromptLoader` raises `FileNotFoundError`

#### Scenario: Unsafe prompt name is rejected
- **WHEN** a prompt name is empty, absolute, or contains a path separator
- **THEN** `PromptLoader` raises `ValueError` before accessing the filesystem

#### Scenario: Prompt examples are not required
- **WHEN** repository prompt files are validated
- **THEN** runtime prompt names such as `system.md`, `reply.md`, `start_topic.md`, `topics.md`, and `wind_down_hint.md` exist without requiring matching `*.example.md` files

### Requirement: Prompt composition
The system SHALL compose generated-task prompts from base prompt, cached bot persona, and optional exchange context including scheduled group context.

#### Scenario: Base prompt and persona are combined
- **WHEN** a base prompt and persona are available
- **THEN** the composed prompt contains the stripped base prompt followed by stripped persona separated by a blank line

#### Scenario: Unchanged persona uses cached text
- **WHEN** the same validated persona file is composed again without a file signature change
- **THEN** cached persona text is reused

#### Scenario: Changed persona is refreshed
- **WHEN** a cached persona file changes its modification timestamp or size
- **THEN** the next composition includes the new persona contents

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
