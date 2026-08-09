# Startup Swarm Availability Refresh

## Purpose

Rebuild the persisted availability snapshot for enabled userbots at startup.

## Requirements

### Requirement: Fresh startup availability snapshot
Before constructing the active swarm pool, the system SHALL clear the previous availability rows and create a fresh persisted availability result for every enabled bot configured in `settings.toml`.

#### Scenario: Removed bot is absent from snapshot
- **WHEN** a bot id exists in persisted availability but no longer exists in `settings.toml`
- **THEN** the startup reset removes its row and does not recreate it

#### Scenario: Every enabled bot receives a result
- **WHEN** startup processes enabled configured bot profiles
- **THEN** persistence contains one current availability result for each processed bot

### Requirement: Startup eligibility criteria
The system SHALL mark a bot available only when Telegram accepts the non-publishing global messaging check, does not report a frozen/deactivated/revoked/globally banned account, and reports `can_write=True` for every enabled group.

#### Scenario: Bot passes all checks
- **WHEN** an enabled bot passes the global account check and can write to every enabled group
- **THEN** its persisted result has `is_available=true` and it joins the active swarm pool

#### Scenario: Ineligible bot
- **WHEN** Telegram reports a frozen/global restriction or any enabled group has unavailable write permission
- **THEN** its persisted result has `is_available=false` with a non-secret reason and the bot is excluded from the active pool

### Requirement: Bounded asynchronous startup checks
The system SHALL perform independent startup availability checks using bounded asyncio concurrency and SHALL not use worker threads for Telethon or SQLite.

#### Scenario: Multiple enabled bots are configured
- **WHEN** startup has more than one enabled bot to check
- **THEN** checks are scheduled asynchronously without exceeding the concurrency bound
