## MODIFIED Requirements

### Requirement: Production persona inventory matches production settings
The system SHALL keep production persona files aligned with the enabled production swarm bot roster declared in `config/settings.prod.toml`.

#### Scenario: Configured production persona files exist
- **WHEN** `config/settings.prod.toml` declares production `[[swarm.bots]]` entries
- **THEN** every configured `persona_file` exists under `ai/prompts/bots`

#### Scenario: Unused production persona files are absent
- **WHEN** production persona files under `ai/prompts/bots` are compared with `config/settings.prod.toml`
- **THEN** every committed production persona file is referenced by at least one production bot entry
