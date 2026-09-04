## MODIFIED Requirements

### Requirement: Fresh availability determines startup pool
The system SHALL replace only the transient startup availability snapshot before checking enabled bot profiles, preserve durable quarantine rows, and admit a profile only after the global Telegram eligibility check and `can_write=True` for every enabled group. When building the startup pool, durable quarantine SHALL be limited to the bot IDs present in the current enabled profile configuration, matched as exact strings.

#### Scenario: Startup ignores quarantine rows for retired profiles
- **WHEN** durable quarantine contains an account ID that is absent from the current TOML bot profiles
- **THEN** startup SHALL leave that row in SQLite but SHALL NOT exclude any current profile because of it

#### Scenario: Startup filters numeric IDs exactly
- **WHEN** durable quarantine contains configured bot IDs represented by numeric strings of different lengths
- **THEN** startup SHALL exclude each exact matching configured ID and SHALL not coerce, truncate, or merge the values
