## Why
Все configured модели отвечают 404, но успешная загрузка каталога маскирует отсутствие генерации и runtime запускает Telegram/scheduler. Логи не объясняют причину отказа.
## What Changes
- Отделить generation_available от статуса записи каталога.
- Не запускать runtime при отсутствии подтверждённой генерации; закрыть SQLite и SDK.
- Добавить безопасную классификацию ошибок маршрутизации без свободного текста провайдера.
- Убрать require_parameters=True: live SDK проверка Gemma с этим фильтром возвращает 404, без него при data_collection=deny получает текст.
## Capabilities
### New Capabilities
Нет.
### Modified Capabilities
- `prompt-and-generation`: совместимость provider routing.
- `swarm-runtime`: проверка готовности OpenRouter перед Telegram.
## Impact
ai/openrouter.py, ai/openrouter_catalog.py, run.py, тесты и README.
