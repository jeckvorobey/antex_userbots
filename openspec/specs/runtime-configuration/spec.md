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
The system SHALL load instance settings only from the supported TOML sections: `[telegram]`, `[[groups]]`, `[groups.schedule]`, `[openrouter]`, `[logging]`, `[swarm.security]`, `[swarm.schedule]`, `[swarm.orchestrator]`, and `[[swarm.bots]]`.

#### Scenario: Minimal configuration requires Telegram credentials and OpenRouter models
- **WHEN** TOML includes `[telegram]` with valid `api_id` and `api_hash` and `[openrouter]` with valid models
- **THEN** `Settings` exposes Telegram credentials and runtime defaults for omitted stable paths and optional sections

#### Scenario: Missing Telegram credentials fail validation
- **WHEN** TOML omits `[telegram]`, `telegram.api_id`, or `telegram.api_hash`
- **THEN** settings validation fails before runtime initialization

#### Scenario: Invalid Telegram credentials fail validation
- **WHEN** `telegram.api_id` is not a positive integer or `telegram.api_hash` is blank
- **THEN** settings validation fails before runtime initialization

#### Scenario: Optional override sections populate runtime fields
- **WHEN** TOML includes supported OpenRouter temperature, logging, security, schedule, or orchestrator fields
- **THEN** `Settings` exposes those values together with computed defaults for omitted sections

#### Scenario: Removed legacy and Gemini sections are rejected
- **WHEN** TOML includes removed sections or keys such as `[gemini]`, `[app]`, `[storage]`, `[prompts]`, `[target]`, `[paths]`, `[telegram].whitelist_user_ids`, `[swarm].enabled`, `[swarm].max_parallel_bots`, `[swarm].ignore_messages_from_swarm`, `[swarm].reply_only_to_addressed_bot`, `[swarm.schedule].pair_cooldown_slots`, or prompt example bootstrap settings
- **THEN** settings validation fails instead of silently accepting them

### Requirement: Production prompt files are tracked
The system SHALL treat configured prompt files as repository-managed production instance files.

#### Scenario: Gitignore allows prompt files
- **WHEN** the repository ignore rules are evaluated
- **THEN** runtime prompt, topic, and persona `.md` files under `ai/prompts/` are not ignored

### Requirement: Environment-backed secrets stay outside TOML
The system SHALL load `OPENROUTER_API_KEY`, optional shared `PROXY`, and per-bot Telethon session strings from environment sources, while loading Telegram API credentials from `config/settings.toml` by default.

#### Scenario: Telegram environment variables are ignored
- **WHEN** environment contains `API_ID` or `API_HASH`
- **THEN** those values do not provide or override Telegram credentials

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

### Requirement: Masked provider secret representation
The system SHALL represent the OpenRouter API key and optional shared proxy as masked secret values throughout configuration loading and reload, and SHALL reveal their raw values only when constructing the external clients that require them.

#### Scenario: Settings representation masks secrets
- **WHEN** settings contain a non-empty OpenRouter key or credential-bearing proxy
- **THEN** their string and representation forms do not expose the raw values

#### Scenario: OpenRouter construction receives raw values
- **WHEN** runtime constructs the OpenRouter client
- **THEN** it unwraps and passes the exact configured API key and optional proxy to that constructor

#### Scenario: Telethon construction receives raw proxy
- **WHEN** runtime constructs a Telethon client with a configured shared proxy
- **THEN** it unwraps and passes the exact proxy URL to the Telegram client wrapper

#### Scenario: Settings reload preserves masked secrets
- **WHEN** the TOML watcher reloads settings
- **THEN** the replacement settings retain masked OpenRouter key and proxy values with the same underlying contents

### Requirement: Patched cryptography dependency
The resolved production dependency set SHALL use `cryptography` version 50.0.0 or newer.

#### Scenario: Dependency audit uses patched cryptography
- **WHEN** production dependencies are resolved and audited
- **THEN** the environment does not contain `cryptography 49.0.0` or report `PYSEC-2026-3552`

### Requirement: Production settings resolve production bot sessions
The system SHALL require operator-owned `config/settings.prod.toml`, when present, to use the current OpenRouter contract before deployment.

#### Scenario: Legacy production provider config is rejected
- **WHEN** a production TOML still contains `[gemini]` or lacks valid `[openrouter].models`
- **THEN** strict settings validation fails until the operator migrates that untracked file

#### Scenario: Migrated production sessions resolve
- **WHEN** production TOML contains valid OpenRouter models and its `session_env` names exist as non-empty environment values
- **THEN** strict settings loading resolves each configured bot session without storing session values in TOML

### Requirement: Stable runtime defaults are code-managed
The system SHALL provide code-managed defaults for repository-stable paths, logging, OpenRouter timeout, and retry policy while requiring operators to choose model slugs.

#### Scenario: Default paths are applied when sections are omitted
- **WHEN** TOML omits storage and prompt path sections
- **THEN** `Settings` uses `data/history.db`, `ai/prompts`, `ai/prompts/topics.md`, and `ai/prompts/bots`

#### Scenario: OpenRouter transport defaults are fixed
- **WHEN** valid OpenRouter models are loaded
- **THEN** runtime uses a 45-second timeout and the code-managed bounded retry policy

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

### Requirement: Shared proxy transport compatibility
The system SHALL accept a shared proxy only when its scheme is supported by both Telegram and the OpenRouter HTTP transport.

#### Scenario: SOCKS4 proxy is rejected
- **WHEN** `PROXY` uses the `socks4` scheme
- **THEN** settings validation fails before any external client is constructed

#### Scenario: Common proxy schemes remain accepted
- **WHEN** `PROXY` uses `http` or `socks5`
- **THEN** the validated secret value is available to both clients

#### Scenario: One transport rejects a proxy scheme
- **WHEN** `PROXY` uses `https`, `socks4`, or `socks5h`
- **THEN** settings validation fails before any external client is constructed

### Requirement: Reloaded safety limits apply immediately
The system SHALL apply reloaded output-length and mention-count limits to the shared generation client before subsequent publishing work.

#### Scenario: Reload tightens output limits
- **WHEN** TOML reload lowers `max_output_chars` or `max_mentions_per_message`
- **THEN** subsequent reply and scheduled output validation uses the new limits without restart

### Requirement: Failed reload remains retryable
The settings watcher SHALL advance its observed file signature only after a changed configuration loads successfully.

#### Scenario: Non-atomic TOML write is temporarily invalid
- **WHEN** reload parsing fails for a changed file and the same file signature is checked again
- **THEN** the watcher retries loading rather than treating that signature as applied

### Requirement: Output cap supports mandatory fallbacks
The system SHALL reject `max_output_chars` values smaller than every mandatory local fallback message.

#### Scenario: Output cap is too small
- **WHEN** TOML configures `max_output_chars` below the minimum supported fallback length
- **THEN** settings validation fails before runtime starts
