## MODIFIED Requirements

### Requirement: Settings reload detection
The system SHALL detect TOML file changes without mutating the existing settings instance and SHALL preserve only original environment or constructor group fallback values across reloads, never group values derived from the previous TOML document.

#### Scenario: Unchanged settings are not reloaded
- **WHEN** the settings file modification time has not changed
- **THEN** the watcher returns no replacement settings

#### Scenario: Changed settings are reloaded
- **WHEN** the settings file modification time changes
- **THEN** the watcher loads a new settings instance for the same environment context and rereads Telegram credentials from TOML

#### Scenario: All TOML groups are removed
- **WHEN** a reload removes every `[[groups]]` entry and no original environment group fallback was configured
- **THEN** the replacement settings expose no groups instead of synthesizing a legacy group from the previous TOML state
