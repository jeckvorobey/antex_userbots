## MODIFIED Requirements

### Requirement: Runtime context initialization
The system SHALL initialize one shared SQLite connection and one shared provider-neutral AI client before starting swarm clients, and SHALL close both exactly once during shutdown.

#### Scenario: Runtime dependencies are created
- **WHEN** the application starts with valid settings
- **THEN** SQLite stores, prompt loading, topic selection, prompt composition, and one shared OpenRouter-backed `ai_client` are initialized before bot clients

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
