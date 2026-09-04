## MODIFIED Requirements

### Requirement: Strict TOML sections
The system SHALL load non-secret settings only from the supported TOML sections: `[app]`, `[[groups]]`, `[storage]`, `[prompts]`, `[gemini]`, `[logging]`, `[swarm.schedule]`, `[swarm.orchestrator]`, and `[[swarm.bots]]`.

#### Scenario: Supported sections populate runtime fields
- **WHEN** TOML includes supported storage, prompts, Gemini, logging, groups, schedule, orchestrator, and bot fields
- **THEN** `Settings` exposes the corresponding runtime values

#### Scenario: Removed legacy sections are rejected
- **WHEN** TOML includes removed legacy sections or keys such as `[target]`, `[paths]`, `[telegram]`, `[swarm].enabled`, `[swarm].max_parallel_bots`, `[swarm].ignore_messages_from_swarm`, `[swarm].reply_only_to_addressed_bot`, `[swarm.schedule].pair_cooldown_slots`, or prompt example bootstrap settings
- **THEN** settings validation fails instead of silently accepting them

## ADDED Requirements

### Requirement: Production prompt files are tracked
The system SHALL treat configured prompt files as repository-managed production instance files.

#### Scenario: Gitignore allows prompt files
- **WHEN** the repository ignore rules are evaluated
- **THEN** runtime prompt, topic, and persona `.md` files under `ai/prompts/` are not ignored
