# Project Overview

`tg_userbot` is a Python 3.11+ Telegram userbot that runs multiple Telethon user accounts in one `swarm` process. The application is started through `run.py`, keeps enabled accounts online across multiple configured Telegram groups, routes addressed human replies to the matching account, starts scheduled `A -> B` bot exchanges per group, persists message and exchange state in SQLite, and uses Gemini for generated text.

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
  -> shared topic intent selection
  -> city-aware start-topic adaptation
  -> bot/topic/question anti-repeat
  -> PromptComposer start_topic/reply prompts
  -> GeminiClient start_topic/generate_reply
  -> Telegram send_message
  -> MessageHistory and ExchangeStore state updates
```

## Configuration Model

Secrets are loaded from `.env` or process environment: `API_ID`, `API_HASH`, `GEMINI_API_KEY`, optional `PROXY_URL`, optional `SETTINGS_PATH`, and per-bot `SESSION_STRING_*` variables referenced by `[[swarm.bots]].session_env`. `GROUP_CHAT_ID` and `GROUP_TARGET` are legacy environment overrides only and are not part of the example configuration.

Non-secret settings are loaded from TOML through strict pydantic models. Supported TOML sections are `[app]`, `[[groups]]`, `[groups.schedule]`, `[storage]`, `[prompts]`, `[gemini]`, `[logging]`, `[swarm.schedule]`, `[swarm.orchestrator]`, and `[[swarm.bots]]`. The only supported app mode is `swarm`. Global `[swarm.schedule]` values are defaults; group-level schedule fields override only the values they define. The runtime watches TOML `mtime` and reloads group enable/disable/add changes without mutating the old settings instance. Prompt, topic, and persona `.md` files under `ai/prompts/` are repository-managed production instance files.

## Data Storage

SQLite is the only persistent storage. `MessageHistory` manages the `messages` table using Telegram `chat_id` as group scope. `ExchangeStore` manages the `scheduled_exchanges` table and persisted group-scoped anti-repeat state for scheduled exchanges, including `group_id` and `group_chat_id`.

## Development Rules

- Follow `AGENTS.md`.
- Prefer TDD for behavior changes.
- Mock Gemini, Telethon, and SQLite filesystem dependencies in tests.
- Keep DB and network operations async.
- Do not hardcode prompts in code.
- Load bot persona strictly from configured `persona_file` under `bot_profiles_dir`.
- Do not log or commit `SESSION_STRING_*`, API keys, private invite hashes, or runtime profile artifacts.
- For new features, large changes, architecture changes, API changes, database changes, data-format changes, or public behavior changes, use the OpenSpec workflow described in `AGENTS.md`.
