# Project Overview

`tg_userbot` is a Python 3.11+ Telegram userbot that runs multiple Telethon user accounts in one `swarm` process. The application is started through `run.py`, keeps enabled accounts online across multiple configured Telegram groups, routes addressed human replies to the matching account, starts scheduled `A -> B` bot exchanges per group, persists message and exchange state in SQLite, and uses OpenRouter for generated text.

## Repository

The canonical Git repository is `git@github.com:jeckvorobey/antex_userbots.git`. The repository uses the `origin` remote only; mirror remotes are not part of the project configuration.

## Stack

- Python 3.11+
- Telethon for Telegram MTProto user sessions
- Official OpenRouter SDK (`openrouter`) for async Chat Completions
- HTTPX with SOCKS support for optional OpenRouter proxy transport
- APScheduler for periodic orchestrator ticks
- aiosqlite for message history and scheduled exchange state
- pydantic-settings and TOML for configuration
- pytest and pytest-asyncio for tests

## Runtime Architecture

```text
run.py
  -> core.config.Settings
  -> RuntimeContext
       -> ai.history.MessageHistory
       -> ai.prompt_loader.PromptLoader
       -> ai.openrouter.OpenRouterClient through ai.generation.TextGenerationClient
       -> userbot.scheduler.TopicSelector
       -> ai.prompt_composer.PromptComposer
       -> userbot.exchange_store.ExchangeStore
  -> userbot.swarm_manager.SwarmManager
       -> userbot.client.UserBotClient per enabled bot (global messaging health-check before active-pool registration)
       -> userbot.reply_router.AddressedReplyRouter per active bot
  -> SettingsReloadWatcher
  -> userbot.orchestrator.SwarmOrchestrator per enabled group scheduled by APScheduler tick
```

Startup model diagnostics reuse the shared OpenRouter SDK client and request builder, with a per-model deadline, before Telegram clients start. Only bounded, secret-redacted check answers enter logs; generated conversation content is not logged.

## Runtime Flows

### Addressed human reply

```text
Telegram NewMessage reply in enabled configured group
  -> AddressedReplyRouter
  -> SwarmManager human slot
  -> MessageHistory session history
  -> PromptComposer reply prompt + persona
  -> TextGenerationClient.generate_reply
  -> Telegram reply
  -> MessageHistory saves user and assistant records
```

### Scheduled exchange

```text
APScheduler tick
  -> settings mtime reload check
  -> enabled groups iteration
  -> SwarmOrchestrator.run_once for group context
  -> ExchangeStore group-scoped due responder check
  -> group active UTC window and human-activity checks
  -> shared ExchangeStore planning lock
  -> group-scoped window check and 24-hour cross-group metadata summary
  -> ExchangeDiversity participant ranking and topic/initial-scenario preferences
  -> persist planned participants/topic and release planning lock
  -> city-aware start-topic adaptation
  -> bot/topic/question anti-repeat
  -> PromptComposer start_topic/reply prompts
  -> TextGenerationClient start_topic/generate_reply
  -> Telegram send_message
  -> MessageHistory and ExchangeStore state updates
```

## Configuration Model

Environment-backed secrets are loaded from `.env` or process environment: `OPENROUTER_API_KEY`, optional shared `PROXY`, optional `SETTINGS_PATH`, and per-bot `SESSION_STRING_*` variables referenced by `[[swarm.bots]].session_env`. Telegram `api_id` and `api_hash` are loaded from the required `[telegram]` TOML section; legacy `API_ID` and `API_HASH` environment values are ignored. The same `PROXY` is applied to Telethon and OpenRouter; when absent, both connect directly. `GROUP_CHAT_ID` and `GROUP_TARGET` are legacy environment overrides only and are not part of the example configuration.

Instance settings are loaded from TOML through strict pydantic models. Supported TOML sections are required `[telegram]`, `[[groups]]`, `[groups.schedule]`, required `[openrouter]`, `[logging]`, `[swarm.schedule]`, `[swarm.orchestrator]`, `[swarm.security]`, and `[[swarm.bots]]`. `[openrouter].models` contains at least two unique non-empty slugs in primary-to-fallback order; optional `temperature` is omitted from requests when absent. Every request requires ZDR providers, denies data collection, enables provider fallback, and requires parameter support. Timeout is 45 seconds and SDK retries are bounded to 15 seconds of exponential backoff for connection, timeout, 408, 429, 5xx, 524, and 529 failures. The only supported app mode is the internal `swarm` default. Global schedule values are inherited by groups. Runtime watches TOML `mtime` and reloads group changes without mutating the old settings instance. Prompt, topic, and persona files are repository-managed.

## Data Storage

SQLite is the only persistent storage. `storage.sqlite_database.SQLiteDatabase` owns one `aiosqlite.Connection` and one asynchronous transaction lock for the entire runtime, configures WAL and busy timeout, retries only temporary lock errors, and is closed once by `RuntimeContext`. Reads and writes use the same lock so another coroutine cannot observe an unfinished write transaction on the shared connection. `MessageHistory` manages the `messages` table using Telegram `chat_id` as group scope. `ExchangeStore` manages the `scheduled_exchanges` table and persisted group-scoped anti-repeat state for scheduled exchanges, including `group_id`, `group_chat_id`, and `last_activity_at` as the indexed sort key for recent/latest exchange lookups. Both stores receive the same database dependency and never open or close their own connection.

`ExchangeStore` also stores quarantine records for accounts that Telegram has confirmed as globally unavailable for messaging. Startup reads these records before creating clients, so a quarantined account cannot be automatically reused until it is manually reviewed and its quarantine record is removed.

Cross-group scheduling reads metadata only from exchanges whose `last_activity_at` is within the last 24 hours, using an index on that column. Planned roles reserve participants; started exchanges retain the pending responder reservation; terminal records count only roles with published message ids. Group identity uses real chat id with group id as a legacy fallback. Text histories and published-only local cooldown remain group-scoped. `userbot.exchange_diversity.ExchangeDiversity` aggregates the metadata once per decision and ranks pairs by other-group unordered-pair use, local cooldown relaxation, other-group participant use, total participant use, then role use. Ties are random; shortages degrade to the lowest-conflict available pair. Local candidate selection remains linear; pair ranking is O(B²), or 182 directed candidates for 14 bots.

The shared `ExchangeStore.planning_lock` serializes the window check, summary read, selection and plan creation within one swarm process, separately from the SQLite transaction lock. It is released before Telegram/LLM calls and scheduled waits. Participant reassignment uses the same coordination and ranking with the counterpart fixed, excluding its own record. Existing plans survive restarts without rerolling their choices. Multiple independent processes sharing one runtime database are not supported by this coordination.

Important-service exchanges are stored in the same `scheduled_exchanges` lifecycle as ordinary exchanges with `exchange_kind = important_service` and an `important_scenario` key. Their cadence is evaluated per group by UTC calendar days: after a group receives an important-service exchange on day N, the next one for that group is eligible no earlier than day N+3. The scenario cycle is `exchange_rub` -> `booking_airbnb` -> `exchange_usdt` -> `booking_booking`, and important-service prompt contexts use `important_service_question` / `important_service_answer` markers so only important answers are required to mention `@tt_exchenge_bot`.

A group's initial service scenario is randomly selected among the least used/reserved keys in other groups over 24 hours; its existing persisted cycle then continues from that position. Ordinary topics retain local freshness priority and use other-group topic counts to rank eligible alternatives. Neither policy changes active windows or responder delays or guarantees semantic uniqueness of generated wording.

## Development Rules

- Follow `AGENTS.md`.
- Prefer TDD for behavior changes.
- Mock OpenRouter, Telethon, and SQLite filesystem dependencies in tests.
- Keep DB and network operations async.
- Do not hardcode prompts in code.
- Load bot persona strictly from configured `persona_file` under `bot_profiles_dir`.
- Do not log or commit `SESSION_STRING_*`, API keys, private invite hashes, or runtime profile artifacts.
- For new features, large changes, architecture changes, API changes, database changes, data-format changes, or public behavior changes, use the OpenSpec workflow described in `AGENTS.md`.
