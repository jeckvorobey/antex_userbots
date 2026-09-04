# Runtime Configuration Delta

## MODIFIED Requirements

### Requirement: Strict TOML sections
The system SHALL load instance settings only from the supported TOML sections: `[telegram]`, `[[groups]]`, `[groups.schedule]`, `[openrouter]`, `[logging]`, `[swarm.security]`, `[swarm.schedule]`, `[swarm.orchestrator]`, and `[[swarm.bots]]`.

#### Scenario: Minimal configuration requires Telegram credentials and OpenRouter models
- **WHEN** TOML includes `[telegram]` with valid `api_id` and `api_hash` and `[openrouter]` with valid models
- **THEN** `Settings` exposes Telegram credentials and runtime defaults for omitted optional sections

#### Scenario: Missing Telegram credentials fail validation
- **WHEN** TOML omits `[telegram]`, `telegram.api_id`, or `telegram.api_hash`
- **THEN** settings validation fails before runtime initialization

#### Scenario: Invalid Telegram credentials fail validation
- **WHEN** `telegram.api_id` is not a positive integer or `telegram.api_hash` is blank
- **THEN** settings validation fails before runtime initialization

#### Scenario: Removed legacy sections are rejected
- **WHEN** TOML includes removed sections or keys not present in the current contract
- **THEN** settings validation fails instead of silently accepting them

### Requirement: Environment-backed secrets stay outside TOML
The system SHALL load `OPENROUTER_API_KEY`, optional shared `PROXY`, and per-bot Telethon session strings from environment sources, while loading Telegram API credentials from `config/settings.toml` by default.

#### Scenario: Telegram environment variables are ignored
- **WHEN** environment contains `API_ID` or `API_HASH`
- **THEN** those values do not provide or override Telegram credentials

#### Scenario: OpenRouter key remains required
- **WHEN** settings are loaded without a non-empty `OPENROUTER_API_KEY`
- **THEN** validation fails before runtime initialization

#### Scenario: Per-bot sessions remain environment-backed
- **WHEN** `[[swarm.bots]].session_env` names a non-empty environment value
- **THEN** bot runtime config contains the stripped session string without storing it in TOML

### Requirement: Settings reload detection
The system SHALL detect TOML file changes without mutating the existing settings instance and SHALL reload Telegram credentials from the changed TOML.

#### Scenario: Changed Telegram credentials are reloaded
- **WHEN** the settings file modification time changes and `[telegram]` contains updated valid credentials
- **THEN** the watcher returns a new settings instance exposing the updated `api_id` and `api_hash`
