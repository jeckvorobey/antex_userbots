## MODIFIED Requirements

### Requirement: Production persona inventory matches production settings
The system SHALL keep production persona files aligned with the enabled production swarm bot roster declared in `config/settings.prod.toml`, including Kirill Orlov only after his local session environment variable is available.

#### Scenario: Configured production persona files exist
- **WHEN** `config/settings.prod.toml` declares production `[[swarm.bots]]` entries
- **THEN** every configured `persona_file` exists under `ai/prompts/bots`

#### Scenario: Unused production persona files are absent
- **WHEN** production persona files under `ai/prompts/bots` are compared with `config/settings.prod.toml`
- **THEN** every committed production persona file is referenced by at least one production bot entry

#### Scenario: Kirill is added atomically
- **WHEN** Kirill's local non-empty `SESSION_STRING_*` variable is available
- **THEN** `kirill_orlov.md`, one enabled production bot entry, and its session environment name are added together without committing the session value

### Requirement: Production persona profiles are detailed and structured
The system SHALL provide concise Markdown persona deltas with enough biographical and behavioral evidence for stable, recognizable character generation while inheriting common rules from the system prompt.

#### Scenario: Required persona delta sections are present
- **WHEN** a production persona profile is read
- **THEN** it includes biography, character and decisions, experience and topics, communication style, typical dialogue moves, boundaries and imperfections, and relationships

#### Scenario: Persona profile is non-trivial
- **WHEN** a production persona profile is read
- **THEN** every section contains character-specific content rather than an empty heading or generic placeholder

#### Scenario: Common policy is not duplicated
- **WHEN** production persona profiles are compared with `system.md`
- **THEN** general length, safety, anti-repeat, promotion, tool honesty, and identity-challenge rules are defined in the shared prompt rather than copied into every persona

### Requirement: Production persona profiles are individually recognizable
The system SHALL make each production persona distinguishable through biography, competence boundaries, decision patterns, speech behavior, and imperfections without relying only on the character name.

#### Scenario: Persona profiles are not duplicate templates
- **WHEN** production persona descriptive bodies are compared
- **THEN** each profile contains a unique combination of biography, experience, decisions, dialogue moves, and imperfections

#### Scenario: Persona has bounded firsthand experience
- **WHEN** a persona describes personal experience or professional competence
- **THEN** it limits first-person claims to the biography and experience explicitly present in that persona

#### Scenario: Sensitive missing facts are not invented
- **WHEN** missing biographical details are expanded
- **THEN** the profile does not invent medical, political, legal, intimate, precise-address, contact, credential, or exact-identifier data

### Requirement: Production persona communication style starts naturally
The system SHALL describe production persona communication styles so bot messages can start like ordinary human chat messages without a repeated character catchphrase.

#### Scenario: Communication style avoids marker opener habits
- **WHEN** a production persona profile is read
- **THEN** its communication style does not prescribe `кстати`, `слушай`, `слушайте`, `смотри`, or another phrase as a habitual opener

#### Scenario: Communication style includes a character-specific start
- **WHEN** a production persona profile describes communication style
- **THEN** it identifies a natural direct answer, question, greeting, or immediate reaction pattern that differs materially from other personas
