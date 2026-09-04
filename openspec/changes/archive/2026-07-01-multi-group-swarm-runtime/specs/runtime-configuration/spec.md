## MODIFIED Requirements

### Requirement: Strict TOML sections
The system SHALL load non-secret settings only from the supported TOML sections: `[app]`, `[[groups]]`, `[storage]`, `[prompts]`, `[gemini]`, `[logging]`, `[swarm.schedule]`, `[swarm.orchestrator]`, and `[[swarm.bots]]`.

#### Scenario: Supported sections populate runtime fields
- **WHEN** TOML includes supported storage, prompts, Gemini, logging, groups, schedule, orchestrator, and bot fields
- **THEN** `Settings` exposes the corresponding runtime values

#### Scenario: Removed legacy sections are rejected
- **WHEN** TOML includes removed legacy sections or keys such as `[target]`, `[paths]`, `[telegram]`, `[swarm].enabled`, `[swarm].max_parallel_bots`, `[swarm].ignore_messages_from_swarm`, `[swarm].reply_only_to_addressed_bot`, or `[swarm.schedule].pair_cooldown_slots`
- **THEN** settings validation fails instead of silently accepting them

### Requirement: Secrets stay outside TOML
The system SHALL load Telegram API credentials, Gemini API key, optional proxy, optional settings path, and per-bot Telethon session strings from environment sources.

#### Scenario: Per-bot session string resolution
- **WHEN** `[[swarm.bots]].session_env` names an environment variable containing a non-empty session string
- **THEN** the bot runtime config contains the stripped session string

#### Scenario: Missing per-bot session string fails clearly
- **WHEN** a configured bot references a missing or empty `session_env`
- **THEN** settings loading fails with the missing environment variable name

## ADDED Requirements

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
