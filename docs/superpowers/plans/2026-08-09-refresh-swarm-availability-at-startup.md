# Refresh Swarm Availability At Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the persisted availability of enabled userbots at every startup.

**Architecture:** SQLite stores a fresh per-bot startup result. The manager starts enabled profiles with bounded asyncio concurrency; the existing non-publishing Telegram check and per-group permission check decide active-pool admission.

**Tech Stack:** Python 3.11+, Telethon, aiosqlite, pytest-asyncio.

## Global Constraints

- SQLite and network operations stay async.
- Session strings and secrets are neither logged nor committed.
- `enabled = false` remains an explicit configuration opt-out.

### Task 1: Persist availability snapshot

**Files:** `userbot/exchange_store.py`, `tests/test_exchange_store.py`

- [ ] Write failing tests for reset and recording available/unavailable bot results.
- [ ] Implement idempotent columns and async reset/record methods.
- [ ] Run `uv run pytest tests/test_exchange_store.py -q`.

### Task 2: Enforce fresh eligibility

**Files:** `run.py`, `userbot/swarm_manager.py`, `tests/test_runtime.py`, `tests/test_swarm_manager.py`

- [ ] Write failing tests for persisted recovery, frozen account, and denied group permission.
- [ ] Make permission checking return an explicit boolean and reject non-writable/unknown groups.
- [ ] Reset persisted state before startup, record every result, and bound independent checks with asyncio.
- [ ] Run `uv run pytest tests/test_runtime.py tests/test_swarm_manager.py -q`.

### Task 3: Document and verify

**Files:** `README.md`, `openspec/**`

- [ ] Document startup availability semantics.
- [ ] Run `uv run pytest` and `openspec validate --strict --all`.
