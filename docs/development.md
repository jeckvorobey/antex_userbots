# Разработка usbttg

## Технологии

| Компонент | Библиотека | Назначение |
|---|---|---|
| MTProto | `telethon` | Подключение к Telegram как user |
| AI | `openrouter` | Async Chat Completions через OpenRouter |
| HTTP | `httpx[socks]` | Async proxy-транспорт OpenRouter |
| Scheduler | `apscheduler` | Планирование orchestrator tick |
| Database | `aiosqlite` | История сообщений и persisted state |
| Config | `pydantic-settings` | Provider/session secrets из `.env`, Telegram credentials и настройки из TOML |
| Testing | `pytest`, `pytest-asyncio` | TDD и async unit/integration tests |
| Python | `3.11+` | Целевая версия |

## Архитектура

```text
ai/
  generation.py
  history.py
  openrouter.py
  prompt_loader.py
  prompt_composer.py
  prompts/
core/
  config.py
  runtime_models.py
userbot/
  client.py
  swarm_manager.py
  reply_router.py
  orchestrator.py
  exchange_store.py
  scheduler.py
run.py
```

## Поток данных

```text
Human reply в группе
  → reply_router.py
  → per-bot coordinator
  → prompt_composer.py
  → openrouter.py
  → history.py
  → ответ адресованным bot

Scheduled tick
  → orchestrator.py
  → exchange_store.py (persisted anti-repeat state)
  → prompt_composer.py
  → openrouter.py
  → history.py
  → A задаёт вопрос, B отвечает
```

## Важные пути

| Путь | Описание |
|---|---|
| `config/settings.example.toml` | Пример swarm-конфигурации |
| `ai/prompts/topics.md` | Темы для scheduled exchange |
| `ai/prompts/system.md` | Базовый системный промт |
| `ai/prompts/reply.md` | Базовый промт ответа |
| `ai/prompts/start_topic.md` | Базовый промт старта темы |
| `ai/prompts/bots/` | Persona-файлы ботов |
| `.env.example` | Шаблон provider key, proxy и session secrets |


## Проверки и запуск

`uv run pytest` — изолированные тесты; `uv run pytest --collect-only` — сбор тестов при диагностике discovery. Не выполняй оба без причины. Fixtures должны использовать in-memory SQLite и fake/stub Telethon/OpenRouter; не подключайся к настоящим аккаунтам или платной генерации для обычной правки.

`uv sync` устанавливает зависимости, а `uv run python run.py` запускает реальный runtime. Выполняй их только по необходимости и в разрешённом scope. Успешный импорт или health-check не доказывает генерацию текста и работу Telegram.
