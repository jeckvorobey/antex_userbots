## Context

`_run_swarm_mode` defines a scheduler callback that iterates enabled groups and constructs `SwarmOrchestrator` inline. Most constructor dependencies are stable across ticks. Group settings can change only when the settings reload watcher returns new settings.

## Goals / Non-Goals

**Goals:**
- Avoid per-tick orchestrator allocations for unchanged groups.
- Preserve reload semantics and group enable/disable behavior.
- Keep cache invalidation explicit and testable.

**Non-Goals:**
- No caching of Telegram resolve results beyond existing `_resolve_group_target` client cache.
- No scheduler job restructuring.

## Decisions

- Store `dict[group_id, (signature, orchestrator)]` inside `_run_swarm_mode`.
- Build signatures from group id, city, resolved chat id, configured target, schedule values, max turns, and skip-human-activity setting.
- After reload, prune cache keys not present in current enabled groups.

## Risks / Trade-offs

- A stale signature would keep old settings. Mitigation: include all constructor values that can affect behavior and test recreation after reload-sensitive changes.
