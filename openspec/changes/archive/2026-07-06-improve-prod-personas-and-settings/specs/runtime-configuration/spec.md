## ADDED Requirements

### Requirement: Production settings resolve production bot sessions
The system SHALL keep `config/settings.prod.toml` loadable against the production environment variable names declared in `.env.prod`.

#### Scenario: Production settings are valid TOML
- **WHEN** `config/settings.prod.toml` is parsed
- **THEN** parsing succeeds without TOML syntax errors

#### Scenario: Production bot sessions are declared in environment file
- **WHEN** production `[[swarm.bots]]` entries reference `session_env` names
- **THEN** each referenced name exists in `.env.prod`

#### Scenario: Production session keys are represented in settings
- **WHEN** `.env.prod` declares `SESSION_STRING_*` keys
- **THEN** each production session key is referenced by exactly one `[[swarm.bots]]` entry
