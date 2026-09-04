## Context

The application is swarm-only: one process starts multiple Telethon user accounts, registers reply routers, and runs a scheduled orchestrator. Today `Settings` exposes one `group_chat_id/group_target`; `SwarmOrchestrator` uses one target and `ExchangeStore` anti-repeat queries have no group scope.

## Goals / Non-Goals

**Goals:**
- Run the same active bot pool across multiple enabled Telegram groups.
- Keep scheduling, due exchanges, topics, question signatures, and history scoped to the concrete group.
- Support TOML reload for group add/enable/disable without mutating current settings objects.
- Preserve async-only DB/runtime behavior and existing fake-friendly tests.

**Non-Goals:**
- No HTTP or admin UI for group configuration.
- No per-city topics file.
- No per-group bot enablement in this phase; every active bot serves every enabled group.

## Decisions

- Introduce explicit group runtime models. `GroupConfig` represents TOML, `GroupSchedule` stores effective schedule values, and `GroupRuntimeState` tracks resolve status without mutating config.
- Treat `[swarm.schedule]` as defaults and allow group overrides for active windows, initiator offset, responder delay, and max turns. This keeps current scheduling behavior intact for each group.
- Use `group_id` as the logical anti-repeat scope and `group_chat_id` as the Telegram history scope. `ExchangeStore` methods accept optional group parameters for backward compatibility with older tests while new runtime always passes group scope.
- Cache resolved group targets per Telethon client and group id. Scheduled exchanges skip a group until a real target and chat id are available.
- Use one scheduler job that reloads settings and iterates enabled groups, instead of one job per group. This avoids stale jobs when a group is disabled.

## Risks / Trade-offs

- Existing config files with `[target]` will fail validation. Migration is documented in the example and README.
- Telegram invite links may not expose a real chat id until the bot has joined. Scheduled exchange is skipped for that group until resolution succeeds.
- Reload only affects group config in this phase. Bot/session changes still require restart.

## Migration Plan

1. Add tests and schema support for `[[groups]]`.
2. Add group columns to `scheduled_exchanges` via idempotent migration.
3. Update router/orchestrator/store to pass group scope.
4. Update runtime membership and reload orchestration.
5. Update docs and sync/archive the OpenSpec change after validation.
