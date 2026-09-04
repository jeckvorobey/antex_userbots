## MODIFIED Requirements

### Requirement: Runtime context initialization
The system SHALL initialize one shared SQLite database connection and other shared runtime dependencies before starting swarm clients, and SHALL close the SQLite connection exactly once during shutdown.

#### Scenario: Runtime dependencies are created
- **WHEN** the application starts
- **THEN** one SQLite database connection is opened and passed to message history and exchange storage, both tables are initialized, prompt loading is configured, Gemini client is configured, topics are loaded, and prompt composer is created

#### Scenario: Runtime persistence is closed once
- **WHEN** the runtime context shuts down
- **THEN** the shared SQLite database closes its connection once and the message history and exchange store do not close it independently

#### Scenario: Partial initialization cleans up persistence
- **WHEN** runtime context construction fails after opening SQLite
- **THEN** the shared SQLite connection is closed before the initialization error is propagated
