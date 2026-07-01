## MODIFIED Requirements

### Requirement: Swarm-only app mode
The system SHALL support `swarm` as the only application mode and SHALL treat it as an internal default rather than a user-configurable TOML field.

#### Scenario: Runtime defaults to swarm without app section
- **WHEN** settings are loaded without a `[app]` section
- **THEN** the effective mode is `swarm`

#### Scenario: Legacy app section is rejected
- **WHEN** TOML provides a legacy `[app]` section or `mode` field
- **THEN** settings validation fails instead of accepting a redundant mode override

### Requirement: Strict TOML sections
The system SHALL load non-secret settings only from the supported TOML sections: `[[groups]]`, `[groups.schedule]`, `[gemini]`, `[logging]`, `[swarm.schedule]`, `[swarm.orchestrator]`, and `[[swarm.bots]]`.

#### Scenario: Minimal supported sections populate runtime fields
- **WHEN** TOML includes only groups and swarm bot configuration
- **THEN** `Settings` exposes runtime defaults for omitted stable paths and optional sections

#### Scenario: Optional override sections populate runtime fields
- **WHEN** TOML includes supported Gemini, logging, schedule, or orchestrator override fields
- **THEN** `Settings` exposes those override values together with computed defaults for omitted sections

#### Scenario: Removed legacy and bootstrap sections are rejected
- **WHEN** TOML includes removed legacy sections or keys such as `[app]`, `[storage]`, `[prompts]`, `[target]`, `[paths]`, `[telegram]`, `[swarm].enabled`, `[swarm].max_parallel_bots`, `[swarm].ignore_messages_from_swarm`, `[swarm].reply_only_to_addressed_bot`, `[swarm.schedule].pair_cooldown_slots`, or prompt example bootstrap settings
- **THEN** settings validation fails instead of silently accepting them

### Requirement: Secrets stay outside TOML
The system SHALL load Telegram API credentials, Gemini API key, optional proxy, and per-bot Telethon session strings from environment sources, while using `config/settings.toml` as the built-in default settings file path.

#### Scenario: Built-in settings path is used by default
- **WHEN** `Settings` is created without an explicit `settings_path` override and without `SETTINGS_PATH` in environment sources
- **THEN** the runtime reads `config/settings.toml` as the default TOML path

#### Scenario: Per-bot session string resolution
- **WHEN** `[[swarm.bots]].session_env` names an environment variable containing a non-empty session string
- **THEN** the bot runtime config contains the stripped session string

#### Scenario: Missing per-bot session string fails clearly
- **WHEN** a configured bot references a missing or empty `session_env`
- **THEN** settings loading fails with the missing environment variable name

## ADDED Requirements

### Requirement: Stable runtime defaults are code-managed
The system SHALL provide code-managed defaults for repository-stable runtime paths and technical bootstrap values so that a minimal instance config does not need to repeat them.

#### Scenario: Default paths are applied when sections are omitted
- **WHEN** TOML omits storage and prompt path sections
- **THEN** `Settings` uses `data/history.db`, `ai/prompts`, `ai/prompts/topics.md`, and `ai/prompts/bots` as effective runtime paths

#### Scenario: Default Gemini and logging values are applied when sections are omitted
- **WHEN** TOML omits optional `[gemini]` and `[logging]` sections
- **THEN** `Settings` uses built-in model, temperature, retry, timeout, fallback, and log-level defaults
