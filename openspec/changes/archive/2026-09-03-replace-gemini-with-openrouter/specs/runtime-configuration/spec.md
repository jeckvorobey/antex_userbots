## MODIFIED Requirements

### Requirement: Strict TOML sections
The system SHALL load non-secret settings only from the supported TOML sections: `[[groups]]`, `[groups.schedule]`, `[openrouter]`, `[logging]`, `[swarm.security]`, `[swarm.schedule]`, `[swarm.orchestrator]`, and `[[swarm.bots]]`.

#### Scenario: Minimal configuration requires OpenRouter models
- **WHEN** TOML includes groups, swarm bots, and an `[openrouter]` section with valid models
- **THEN** `Settings` exposes runtime defaults for omitted stable paths and optional sections

#### Scenario: Optional override sections populate runtime fields
- **WHEN** TOML includes supported OpenRouter temperature, logging, security, schedule, or orchestrator fields
- **THEN** `Settings` exposes those values together with computed defaults for omitted sections

#### Scenario: Removed legacy and Gemini sections are rejected
- **WHEN** TOML includes removed sections or keys such as `[gemini]`, `[app]`, `[storage]`, `[prompts]`, `[target]`, `[paths]`, `[telegram]`, `[swarm].enabled`, `[swarm].max_parallel_bots`, `[swarm].ignore_messages_from_swarm`, `[swarm].reply_only_to_addressed_bot`, `[swarm.schedule].pair_cooldown_slots`, or prompt example bootstrap settings
- **THEN** settings validation fails instead of silently accepting them

### Requirement: Secrets stay outside TOML
The system SHALL load Telegram API credentials, `OPENROUTER_API_KEY`, optional shared `PROXY`, and per-bot Telethon session strings from environment sources, while using `config/settings.toml` as the built-in default settings file path.

#### Scenario: OpenRouter key is required
- **WHEN** settings are loaded without a non-empty `OPENROUTER_API_KEY`
- **THEN** validation fails before runtime initialization

#### Scenario: Shared proxy is optional
- **WHEN** `PROXY` is absent or blank
- **THEN** effective proxy is `None` and Telethon and OpenRouter use direct connections

#### Scenario: Shared proxy is exposed
- **WHEN** `PROXY` contains a non-empty URL
- **THEN** the same normalized value is available to Telethon and OpenRouter runtime construction

#### Scenario: Legacy secret names are ignored
- **WHEN** environment contains `GEMINI_API_KEY` or `PROXY_URL` without the new required names
- **THEN** they do not satisfy the OpenRouter key or proxy contract

#### Scenario: Built-in settings path is used by default
- **WHEN** `Settings` is created without an explicit `settings_path` override and without `SETTINGS_PATH`
- **THEN** runtime reads `config/settings.toml`

#### Scenario: Per-bot session string resolution
- **WHEN** `[[swarm.bots]].session_env` names a non-empty environment value
- **THEN** bot runtime config contains the stripped session string

#### Scenario: Missing per-bot session string fails clearly
- **WHEN** a bot references a missing or empty `session_env`
- **THEN** settings loading fails with that environment variable name

### Requirement: Production settings resolve production bot sessions
The system SHALL require operator-owned `config/settings.prod.toml`, when present, to use the current OpenRouter contract before deployment.

#### Scenario: Legacy production provider config is rejected
- **WHEN** a production TOML still contains `[gemini]` or lacks valid `[openrouter].models`
- **THEN** strict settings validation fails until the operator migrates that untracked file

#### Scenario: Migrated production sessions resolve
- **WHEN** production TOML contains valid OpenRouter models and its `session_env` names exist as non-empty environment values
- **THEN** strict settings loading resolves each configured bot session without storing session values in TOML

## ADDED Requirements

### Requirement: OpenRouter model configuration
The system SHALL require an ordered list of at least two unique non-empty OpenRouter model slugs and SHALL accept an optional temperature from 0 through 2.

#### Scenario: Model order is preserved
- **WHEN** `[openrouter].models` contains a primary and fallback models
- **THEN** `Settings` exposes the trimmed strings in their original order

#### Scenario: Too few models are rejected
- **WHEN** fewer than two non-empty model slugs are configured
- **THEN** settings validation fails

#### Scenario: Duplicate models are rejected
- **WHEN** model slugs repeat after trimming
- **THEN** settings validation fails

#### Scenario: Temperature remains absent
- **WHEN** `[openrouter]` omits temperature
- **THEN** effective OpenRouter temperature is `None`

## MODIFIED Requirements

### Requirement: Stable runtime defaults are code-managed
The system SHALL provide code-managed defaults for repository-stable paths, logging, OpenRouter timeout, and retry policy while requiring operators to choose model slugs.

#### Scenario: Default paths are applied when sections are omitted
- **WHEN** TOML omits storage and prompt path sections
- **THEN** `Settings` uses `data/history.db`, `ai/prompts`, `ai/prompts/topics.md`, and `ai/prompts/bots`

#### Scenario: OpenRouter transport defaults are fixed
- **WHEN** valid OpenRouter models are loaded
- **THEN** runtime uses a 45-second timeout and the code-managed bounded retry policy
