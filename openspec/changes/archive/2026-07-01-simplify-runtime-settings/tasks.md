## 1. Runtime configuration contract

- [x] 1.1 Обновить тесты конфигурации под новый публичный контракт: default `config/settings.toml`, отсутствие `[app]`, `[storage]`, `[prompts]`, минимальный TOML и сокращённые env expectations
- [x] 1.2 Обновить `core/config.py`, чтобы встроенный default path указывал на `config/settings.toml`, `swarm` mode был внутренним default, а стабильные repo paths и технические defaults вычислялись без обязательных TOML-секций
- [x] 1.3 Сохранить совместимость runtime facade и reload watcher так, чтобы `Settings` по-прежнему отдавал вычисленные `db_path`, `prompts_dir`, `topics_path`, `bot_profiles_dir`, `gemini_*` и `log_level`

## 2. Public config surface

- [x] 2.1 Удалить `SETTINGS_PATH` из стандартного bootstrap-примера в `.env.example` и привести setup flow к встроенному `config/settings.toml`
- [x] 2.2 Сократить `config/settings.example.toml` до минимального пользовательского конфига с `[[groups]]`, `[[swarm.bots]]` и только действительно полезными optional override секциями
- [x] 2.3 Обновить `README.md` и связанную документацию, чтобы breaking changes и миграция со старого конфига были описаны явно

## 3. Verification

- [x] 3.1 Прогнать релевантные тесты конфигурации и runtime bootstrap, обновив или добавив проверки для кодовых defaults и сокращённого TOML-контракта
- [x] 3.2 Проверить, что OpenSpec artifacts, пример конфигурации и документация согласованы между собой и готовы к `openspec-sync-specs` после реализации
