## MODIFIED Requirements

### Requirement: Group runtime registry
The system SHALL maintain runtime state for configured groups separately from immutable configuration and SHALL never synthesize an active legacy group when the current configuration explicitly contains only disabled groups.

#### Scenario: Enabled group becomes active after resolve
- **WHEN** at least one active bot resolves an enabled group to a Telegram target and chat id
- **THEN** the group runtime state is available for routing and scheduled exchanges

#### Scenario: Disabled group stops runtime work
- **WHEN** a reload marks a group disabled
- **THEN** routing and scheduling skip that group without stopping the bot pool

#### Scenario: Every configured group is disabled
- **WHEN** the current configuration contains one or more groups and none of them is enabled
- **THEN** runtime returns no active groups and does not create a legacy fallback from compatibility fields
