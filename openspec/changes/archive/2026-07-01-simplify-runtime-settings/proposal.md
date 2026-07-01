## Why

Текущий runtime-конфиг содержит слишком много явных настроек, которые фактически не являются настройками инстанса, а дублируют стабильную структуру репозитория и кодовые значения по умолчанию. Из-за этого `config/settings.toml` и `.env` перегружены, сложнее читаются и требуют лишних действий при bootstrap нового swarm-инстанса.

## What Changes

- **BREAKING** Убрать `SETTINGS_PATH` из стандартного env/bootstrap-контракта и использовать `config/settings.toml` как путь по умолчанию.
- **BREAKING** Упростить TOML-контракт: убрать обязательную секцию `[app]` и перевести фиксированный `swarm`-mode в кодовый default.
- **BREAKING** Убрать из публичного TOML-контракта секции `[storage]` и `[prompts]`, если они лишь повторяют стандартные repo paths и internal defaults.
- **BREAKING** Сократить публичную секцию `[gemini]` до действительно инстанс-зависимых полей, а retry/timeout/fallback defaults перенести в код.
- Оставить `[[groups]]`, `[[swarm.bots]]`, а также опциональные schedule/orchestrator/logging overrides как основной пользовательский runtime-контракт.
- Обновить документацию, пример конфигурации и тесты так, чтобы минимальный bootstrap-конфиг стал короче и отражал новый контракт.

## Capabilities

### New Capabilities

### Modified Capabilities
- `runtime-configuration`: runtime-конфигурация должна поддерживать компактный минимальный контракт с кодовыми defaults для стабильных путей и bootstrap-настроек

## Impact

- Affected code: `core/config.py`, `run.py`, конфигурационные тесты, runtime tests, `README.md`, `.env.example`, `config/settings.example.toml`
- Affected systems: bootstrap локального запуска, загрузка TOML/env-конфига, reload watcher, documented setup flow
- Public impact: изменится формат рекомендуемого `settings.toml` и `.env` для новых и существующих инстансов
