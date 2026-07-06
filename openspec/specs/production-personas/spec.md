# Production Personas

## Purpose

Define the production bot persona inventory and quality contract for committed persona profiles.

## Requirements

### Requirement: Production persona inventory matches production settings
The system SHALL keep production persona files aligned with the enabled production swarm bot roster declared in `config/settings.prod.toml`.

#### Scenario: Configured production persona files exist
- **WHEN** `config/settings.prod.toml` declares production `[[swarm.bots]]` entries
- **THEN** every configured `persona_file` exists under `ai/prompts/bots`

#### Scenario: Unused production persona files are absent
- **WHEN** production persona files under `ai/prompts/bots` are compared with `config/settings.prod.toml`
- **THEN** every committed production persona file is referenced by at least one production bot entry

### Requirement: Production persona profiles are detailed and structured
The system SHALL provide detailed Markdown persona profiles that include the behavioral dimensions needed for stable, recognizable character generation.

#### Scenario: Required persona sections are present
- **WHEN** a production persona profile is read
- **THEN** it includes sections for character, communication style, chat behavior, group discussion behavior, reactions, thinking style, interests, life context, habits, conflict behavior, restrictions, probabilistic behavior, relationships, and human imperfections

#### Scenario: Persona profile is non-trivial
- **WHEN** a production persona profile is read
- **THEN** it contains enough content to be materially richer than the previous short template

### Requirement: Production persona profiles are individually recognizable
The system SHALL make each production persona distinguishable by style and behavior without relying only on the character name.

#### Scenario: Persona profiles are not duplicate templates
- **WHEN** production persona profiles are compared
- **THEN** their descriptive bodies are not identical and contain character-specific wording

#### Scenario: Persona restrictions prevent generic assistant behavior
- **WHEN** a production persona profile is read
- **THEN** it explicitly forbids AI disclosure, repeated templates, copying other persona styles, and becoming an idealized assistant
