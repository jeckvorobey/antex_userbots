## MODIFIED Requirements

### Requirement: Runtime context initialization
The system SHALL initialize one shared SQLite connection and one shared provider-neutral AI client before starting swarm clients, and SHALL close both exactly once during shutdown.

#### Scenario: Runtime dependencies are created
- **WHEN** the application starts with valid settings
- **THEN** SQLite stores, prompt loading, OpenRouter free-model diagnostics, topic selection, prompt composition, and one shared OpenRouter-backed `ai_client` are initialized before bot clients

#### Scenario: Configured model succeeds
- **WHEN** startup checks configured models
- **THEN** it SHALL send sequential short generation requests in unique configuration order using the file-backed prompt «Ответь только словами: Да, доступен»
- **AND** any nonempty text response after stripping surrounding whitespace SHALL count as success
- **AND** at first success it SHALL stop checks, skip catalog fetching, update diagnostics with catalog_fetched=false, and continue startup without replacing configured models

#### Scenario: All configured models fail
- **WHEN** every configured model returns an HTTP error, timeout, malformed response, empty text, or the list is empty
- **THEN** startup SHALL fetch the free text-output catalog and write sorted connection slugs plus attempted check results to logs/openrouter_free_models.json
- **AND** diagnostic files SHALL omit raw generated text and secrets

#### Scenario: Catalog fails after probes
- **WHEN** the fallback catalog request fails
- **THEN** the safe error report SHALL retain attempted model check results and runtime startup SHALL continue

#### Scenario: Runtime dependencies close once
- **WHEN** runtime shuts down
- **THEN** the AI client and shared SQLite connection each close exactly once

#### Scenario: Partial initialization cleans up resources
- **WHEN** context construction fails after SQLite or the AI client is created
- **THEN** every successfully created owned resource is closed before the error propagates

#### Scenario: Shared proxy reaches both transports
- **WHEN** settings provide `PROXY`
- **THEN** runtime passes the same value to every Telethon client and the OpenRouter AI client

#### Scenario: Direct transports omit proxy
- **WHEN** settings do not provide `PROXY`
- **THEN** runtime constructs Telethon and OpenRouter without proxy configuration

