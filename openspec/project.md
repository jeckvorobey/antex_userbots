# Project Overview

`tg_userbot` is a Python 3.11+ Telegram userbot that runs multiple Telethon user accounts in one `swarm` process. The application is started through `run.py`, keeps enabled accounts online across multiple configured Telegram groups, routes addressed human replies to the matching account, starts scheduled `A -> B` bot exchanges per group, persists message and exchange state in SQLite, and uses Gemini for generated text.

## Repository

The canonical Git repository is `git@github.com:jeckvorobey/antex_userbots.git`. The repository uses the `origin` remote only; mirror remotes are not part of the project configuration.

## Stack

- Python 3.11+
- Telethon for Telegram MTProto user sessions
- Google Gemini SDK (`google-genai`) for text generation
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
       -> ai.gemini.PromptLoader
       -> ai.gemini.GeminiClient
       -> userbot.scheduler.TopicSelector
       -> ai.prompt_composer.PromptComposer
       -> userbot.exchange_store.ExchangeStore
  -> userbot.swarm_manager.SwarmManager
       -> userbot.client.UserBotClient per enabled bot
       -> userbot.reply_router.AddressedReplyRouter per active bot
  -> SettingsReloadWatcher
  -> userbot.orchestrator.SwarmOrchestrator per enabled group scheduled by APScheduler tick
```

## Runtime Flows

### Addressed human reply

```text
Telegram NewMessage reply in enabled configured group
  -> AddressedReplyRouter
  -> SwarmManager human slot
  -> MessageHistory session history
  -> PromptComposer reply prompt + persona
  -> GeminiClient.generate_reply
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
  -> ExchangeStore group-scoped window check
  -> important-service cadence/rotation check or shared topic intent selection
  -> city-aware start-topic adaptation
  -> bot/topic/question anti-repeat
  -> PromptComposer start_topic/reply prompts
  -> GeminiClient start_topic/generate_reply
  -> Telegram send_message
  -> MessageHistory and ExchangeStore state updates
```

## Configuration Model

Secrets are loaded from `.env` or process environment: `API_ID`, `API_HASH`, `GEMINI_API_KEY`, optional `PROXY_URL`, optional `SETTINGS_PATH`, and per-bot `SESSION_STRING_*` variables referenced by `[[swarm.bots]].session_env`. `GROUP_CHAT_ID` and `GROUP_TARGET` are legacy environment overrides only and are not part of the example configuration.

Non-secret settings are loaded from TOML through strict pydantic models. Supported TOML sections are `[[groups]]`, `[groups.schedule]`, `[gemini]`, `[logging]`, `[swarm.schedule]`, `[swarm.orchestrator]`, `[swarm.security]`, and `[[swarm.bots]]`. The only supported app mode is the internal `swarm` default, not a user-configurable TOML field. Global `[swarm.schedule]` values are defaults; group-level schedule fields override only the values they define. The runtime watches TOML `mtime` and reloads group enable/disable/add changes without mutating the old settings instance. Prompt, topic, and persona `.md` files under `ai/prompts/` are repository-managed production instance files. Production persona inventory in `ai/prompts/bots` is expected to match `config/settings.prod.toml`, and `settings.prod.toml` is expected to reference the production `SESSION_STRING_*` keys declared in `.env.prod` without storing secret values in TOML.

## Data Storage

SQLite is the only persistent storage. `MessageHistory` manages the `messages` table using Telegram `chat_id` as group scope. `ExchangeStore` manages the `scheduled_exchanges` table and persisted group-scoped anti-repeat state for scheduled exchanges, including `group_id`, `group_chat_id`, and `last_activity_at` as the indexed sort key for recent/latest exchange lookups.

Important-service exchanges are stored in the same `scheduled_exchanges` lifecycle as ordinary exchanges with `exchange_kind = important_service` and an `important_scenario` key. Their cadence is evaluated per group by UTC calendar days: after a group receives an important-service exchange on day N, the next one for that group is eligible no earlier than day N+3. The scenario cycle is `exchange_rub` -> `booking_airbnb` -> `exchange_usdt` -> `booking_booking`, and important-service prompt contexts use `important_service_question` / `important_service_answer` markers so only important answers are required to mention `@tt_exchenge_bot`.

## Development Rules

- Follow `AGENTS.md`.
- Prefer TDD for behavior changes.
- Mock Gemini, Telethon, and SQLite filesystem dependencies in tests.
- Keep DB and network operations async.
- Do not hardcode prompts in code.
- Load bot persona strictly from configured `persona_file` under `bot_profiles_dir`.
- Do not log or commit `SESSION_STRING_*`, API keys, private invite hashes, or runtime profile artifacts.
- For new features, large changes, architecture changes, API changes, database changes, data-format changes, or public behavior changes, use the OpenSpec workflow described in `AGENTS.md`.
