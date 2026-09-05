## Context
Production startup 2026-09-05: три 404, GET каталога 200, затем штатный запуск.
## Goals / Non-Goals
Не выдавать каталог за рабочую генерацию. Не менять ключи, модели или provider privacy настройки без подтверждённой причины.
## Decisions
Явное generation_available во всех результатах диагностики; runtime требует True. Safe reason определяется по известным фрагментам error.message, но сам message не сохраняется. Успех генерации остаётся успехом даже при ошибке записи отчёта.
## Risks / Trade-offs
При временном отказе startup завершится с ошибкой до Telegram; повторный запуск выполнит новые реальные проверки.

## Подтверждённая причина 404
Локальный SDK probe Gemma: deny без require_parameters дал непустой текст; require_parameters=True без deny дал 404. Убирается только require_parameters, data_collection=deny сохраняется.

После снятия фильтра live check упёрся в 8 секунд: deadline startup теперь равен настроенному request timeout (45 секунд по умолчанию), включая SDK retries.

## Повторная проверка 2026-09-05
Через текущий SDK с локальными настройками MiniMax и Gemma вернули непустой текст; GLM вернул 429. Контрольный запрос Gemma с require_parameters=True вернул HTTP 404 с безопасной категорией unsupported_parameters. В deployed commit 5ee9df7 этот фильтр присутствует.

Coolify использует main и подключает отдельные host-каталоги к /app/config и /app/logs. Поэтому startup выводит выбранный settings_path, model ids и shared_proxy=on/off без секретов. Обновление образа не заменяет смонтированный TOML.

Проверки: 108 targeted tests passed. Полный прогон до добавления конфигурационного лога: 393 passed, 2 failed в неизменённых tests/test_personas.py / persona-файлах; эти проверки не относятся к OpenRouter. Production generation после выкладки должна подтверждаться отдельно.
