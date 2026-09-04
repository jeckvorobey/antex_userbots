## ADDED Requirements

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
