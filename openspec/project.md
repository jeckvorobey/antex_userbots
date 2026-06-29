# Project Overview

`tg_userbot` is a Python 3.11+ Telegram userbot that runs multiple Telethon user accounts in one `swarm` process. The application is started through `run.py`, keeps enabled accounts online, routes addressed human replies to the matching account, starts scheduled `A -> B` bot exchanges, persists message and exchange state in SQLite, and uses Gemini for generated text.

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
  -> userbot.orchestrator.SwarmOrchestrator scheduled by APScheduler
```

## Runtime Flows

### Addressed human reply

```text
Telegram NewMessage reply
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
  -> SwarmOrchestrator.run_once
  -> ExchangeStore due responder check
  -> active UTC window and human-activity checks
  -> ExchangeStore window check
  -> bot/topic/question anti-repeat
  -> PromptComposer start_topic/reply prompts
  -> GeminiClient start_topic/generate_reply
  -> Telegram send_message
  -> MessageHistory and ExchangeStore state updates
```

## Configuration Model

Secrets are loaded from `.env` or process environment: `API_ID`, `API_HASH`, `GEMINI_API_KEY`, optional `PROXY_URL`, optional target overrides, `SETTINGS_PATH`, and per-bot `SESSION_STRING_*` variables referenced by `[[swarm.bots]].session_env`.

Non-secret settings are loaded from TOML through strict pydantic models. Supported TOML sections are `[app]`, `[target]`, `[storage]`, `[prompts]`, `[gemini]`, `[logging]`, `[swarm.schedule]`, `[swarm.orchestrator]`, and `[[swarm.bots]]`. The only supported app mode is `swarm`.

## Data Storage

SQLite is the only persistent storage. `MessageHistory` manages the `messages` table. `ExchangeStore` manages the `scheduled_exchanges` table and persisted anti-repeat state for scheduled exchanges.

## Development Rules

- Follow `AGENTS.md`.
- Prefer TDD for behavior changes.
- Mock Gemini, Telethon, and SQLite filesystem dependencies in tests.
- Keep DB and network operations async.
- Do not hardcode prompts in code.
- Load bot persona strictly from configured `persona_file` under `bot_profiles_dir`.
- Do not log or commit `SESSION_STRING_*`, API keys, private invite hashes, or runtime profile artifacts.
- For new features, large changes, architecture changes, API changes, database changes, data-format changes, or public behavior changes, use the OpenSpec workflow described in `AGENTS.md`.

