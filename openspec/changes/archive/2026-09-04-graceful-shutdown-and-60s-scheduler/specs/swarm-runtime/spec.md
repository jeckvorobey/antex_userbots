## ADDED Requirements

### Requirement: Graceful operator shutdown
The system SHALL treat an operator interrupt at the process entry point as a successful graceful shutdown after asynchronous runtime cleanup completes.

#### Scenario: Ctrl+C stops without traceback
- **WHEN** the operator sends an interrupt while the swarm is running
- **THEN** supervisor tasks are cancelled, owned runtime resources are closed, and the process exits without printing a `CancelledError` or `KeyboardInterrupt` traceback

#### Scenario: Runtime failures remain visible
- **WHEN** the application exits because of an exception other than an operator interrupt
- **THEN** the exception propagates from the process entry point

### Requirement: Scheduler tick cadence
The system SHALL use 60 seconds as the default orchestrator scheduler tick interval and SHALL allow an explicit TOML value to override that default.

#### Scenario: Default scheduler interval
- **WHEN** configuration does not specify `swarm.orchestrator.tick_seconds`
- **THEN** the scheduler registers the orchestrator job with a 60-second interval

#### Scenario: Explicit scheduler interval
- **WHEN** configuration specifies a valid `swarm.orchestrator.tick_seconds`
- **THEN** the scheduler registers the orchestrator job with that configured interval
