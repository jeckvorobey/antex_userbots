## 1. Проверка и реализация
- [x] 1.1 Изменить tests/test_openrouter_catalog.py: первый/последующий успех, непустой текст, все отказы, пустой список, ошибка каталога, безопасность; получить RED через uv run pytest tests/test_openrouter_catalog.py -q.
- [x] 1.2 Изменить ai/openrouter_catalog.py и добавить ai/prompts/model_probe.md; получить GREEN тем же тестом.
## 2. Завершение
- [x] 2.1 Обновить README.md, проверить uv run pytest и git diff --check; review требований и строгая валидация OpenSpec.
- [x] 2.2 Синхронизировать swarm-runtime и архивировать change по правилам проекта после успешных проверок.

## Evidence
- RED: 10 failed, 2 passed; GREEN: 12 passed (tests/test_openrouter_catalog.py).
- Полный прогон: 383 passed, 2 failed в tests/test_personas.py (ожидания текстов persona, неизменённые файлы вне scope).
- Статическое независимое ревью: важных регрессий нет; уточнена формулировка design.
- OpenSpec strict: 15 passed; git diff --check успешно.
- Релевантный прогон adapter/catalog/runtime/logging: 98 passed. Синхронизация swarm-runtime и архивирование завершены.
