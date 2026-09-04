# Scheduled Exchanges — Delta Spec

## Modified Requirement: Bot and topic anti-repeat

### Scenario: Recent bots are excluded when possible (MODIFIED)

- **WHEN** at least two candidates remain after excluding the last **four** scheduled bot ids for the group
- **THEN** the chosen initiator and responder come from the remaining candidates

#### Change from baseline

Baseline spec says "last three". This change increases the exclusion window to the last four unique bots that participated (as initiator or responder) in scheduled exchanges within the current group.

### Scenario: Recent bot filter relaxes when pool is small (UNCHANGED)

- **WHEN** excluding recent bots would leave fewer than two candidates
- **THEN** the orchestrator relaxes the recent-bot exclusion enough to choose a pair

### Scenario: Group scoping is enforced (CLARIFIED)

- **WHEN** the orchestrator selects a bot pair for group A
- **THEN** only scheduled exchange events from group A are considered for the recent-bot cooldown; events from group B do not affect group A's selection
