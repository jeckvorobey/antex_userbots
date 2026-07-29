# Runtime Configuration

## Purpose

Define the supported runtime configuration contract for the swarm-only application.
## Requirements
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

### Requirement: Production prompt files are tracked
The system SHALL treat configured prompt files as repository-managed production instance files.

#### Scenario: Gitignore allows prompt files
- **WHEN** the repository ignore rules are evaluated
- **THEN** runtime prompt, topic, and persona `.md` files under `ai/prompts/` are not ignored

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

### Requirement: Stable runtime defaults are code-managed
The system SHALL provide code-managed defaults for repository-stable runtime paths and technical bootstrap values so that a minimal instance config does not need to repeat them.

#### Scenario: Default paths are applied when sections are omitted
- **WHEN** TOML omits storage and prompt path sections
- **THEN** `Settings` uses `data/history.db`, `ai/prompts`, `ai/prompts/topics.md`, and `ai/prompts/bots` as effective runtime paths

#### Scenario: Default Gemini and logging values are applied when sections are omitted
- **WHEN** TOML omits optional `[gemini]` and `[logging]` sections
- **THEN** `Settings` uses built-in model, temperature, retry, timeout, fallback, and log-level defaults

### Requirement: Multi-group configuration
The system SHALL configure target Telegram chats through `[[groups]]` entries.

#### Scenario: Enabled groups are exposed
- **WHEN** TOML defines multiple groups with ids, cities, enabled flags, and targets
- **THEN** settings expose all configured groups and enabled groups separately

#### Scenario: Duplicate group id is rejected
- **WHEN** two groups have the same id after case-normalization
- **THEN** settings validation fails

#### Scenario: Group without chat id or target is rejected
- **WHEN** a group has neither `group_chat_id` nor `group_target`
- **THEN** settings validation fails

### Requirement: Group schedule inheritance
The system SHALL derive each group schedule from global `[swarm.schedule]` defaults plus group-level overrides.

#### Scenario: Group inherits default schedule
- **WHEN** a group omits schedule override fields
- **THEN** its effective schedule uses the global schedule values

#### Scenario: Group overrides schedule
- **WHEN** a group defines schedule override fields
- **THEN** only those fields replace the global schedule defaults for that group

### Requirement: Settings reload detection
The system SHALL detect TOML file changes without mutating the existing settings instance.

#### Scenario: Unchanged settings are not reloaded
- **WHEN** the settings file modification time has not changed
- **THEN** the watcher returns no replacement settings

#### Scenario: Changed settings are reloaded
- **WHEN** the settings file modification time changes
- **THEN** the watcher loads a new settings instance for the same secrets/environment context

### Requirement: Bot config validation
The system SHALL reject duplicate swarm bot ids and persona paths outside `bot_profiles_dir`.

#### Scenario: Duplicate bot id is rejected
- **WHEN** two configured bots have the same id after case-normalization
- **THEN** settings validation fails

#### Scenario: Unsafe persona path is rejected
- **WHEN** `persona_file` is absolute or contains `..`
- **THEN** settings validation fails

### Requirement: Schedule validation
The system SHALL validate active UTC windows and minute ranges before runtime use.

#### Scenario: Invalid UTC window is rejected
- **WHEN** an active window is not in valid `HH-HH` bounds or has equal start and end in configuration validation
- **THEN** settings validation fails

#### Scenario: Invalid minute range is rejected
- **WHEN** a configured minute range has a negative minimum or a maximum lower than the minimum
- **THEN** settings validation fails

### Requirement: Runtime security settings
The system SHALL support a dedicated `swarm.security` configuration section for abuse throttling, pending reply capacity, LLM gating, output safety, and history retention.

#### Scenario: Security defaults are applied
- **WHEN** the TOML omits the `swarm.security` section
- **THEN** settings expose safe code defaults including a positive per-bot pending reply limit

#### Scenario: Security overrides are applied
- **WHEN** the TOML provides `swarm.security` override fields including `addressed_reply_max_pending_per_bot`
- **THEN** settings expose those overrides as effective runtime security values
