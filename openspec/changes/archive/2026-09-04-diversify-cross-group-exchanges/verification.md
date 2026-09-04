# Проверка diversify-cross-group-exchanges

Дата: 2026-09-04.

Реализованы общая 24-часовая сводка метаданных, ранжирование участников/ролей, сохранённые резервы, координация планирования и замены, разные стартовые service-сценарии и предпочтение обычных тем других групп. README, project.md и основные спецификации синхронизированы.

## Результаты

- До реализации новый регрессионный набор: 18 failed, 1 passed. В частности, 4/2 и 14/3 повторяли одну пару, а замена responder игнорировала другую группу.
- Финальный релевантный прогон: `uv run pytest -q tests/test_cross_group_diversity.py tests/test_orchestrator.py tests/test_exchange_store.py tests/test_scheduler.py tests/test_runtime.py` — **152 passed**.
- Полный прогон: `uv run pytest -q --tb=short` — **365 passed, 2 failed**. Он не считается полностью успешным.
- Падения: `tests/test_personas.py::test_prod_personas_are_detailed_and_structured` и `tests/test_personas.py::test_prod_persona_communication_style_avoids_marker_openers`. Они относятся к обязательным фразам/стилю production persona-файлов. Подтверждены вызовом тех же функций из `HEAD` с тем же локальным production-конфигом; тестовый модуль и persona-файлы побайтово совпадают с `HEAD`. Код планировщика эти проверки не импортируют. Persona-промты и локальный конфиг в рамках задачи не менялись.
- `openspec validate --strict --all` перед архивированием — **15 passed, 0 failed**.
- `git diff --check` — без ошибок.
- Независимое read-only ревью не обнаружило блокирующих ошибок. По замечанию о покрытии добавлен проходящий интеграционный тест замены инициатора с фиксированным responder и конфликтом пары в другой группе.

## Покрытые сценарии

Пулы 4/2 и 14/3 для обычных и service exchanges; 4/5 и исчерпание всех шести пар четырёх ботов; малая доступность; роли и общий баланс; приоритет пары над локальным cooldown; initial scenario exhaustion и существующий N+3/цикл; локальная свежесть и exhaustion тем; конкурентное планирование; сохранение плана при повторном создании orchestrators; ошибка сохранения без phantom reservation; published/reserved lifecycle; inclusive граница 24 часов; реальный chat id и legacy group id; идемпотентная legacy migration и индекс; замена обоих типов участников без повторной отправки опубликованного сообщения.

## Ограничения проверки

Проверки выполнены локально с in-memory SQLite и fake Telegram/LLM. Live Telegram QA, платные вызовы LLM и deployment не выполнялись. Рестарт проверен повторным созданием orchestrators поверх сохранённого store; физический перезапуск production-процесса не выполнялся. Два ранее существовавших persona-падения остаются вне scope этого change.

## Изменённые файлы

- `userbot/exchange_store.py`: общая сводка и planning lock, индекс last_activity_at.
- `userbot/exchange_diversity.py`: агрегаты и ранжирование пар.
- `userbot/orchestrator.py`: интеграция выбора, начальных сценариев, тем и замены.
- `tests/test_cross_group_diversity.py`, `tests/test_orchestrator.py`: регрессии и обновлённый контракт первого сценария.
- `README.md`, `openspec/project.md`: поведение и архитектура.
- `openspec/specs/scheduled-exchanges/spec.md`, `openspec/specs/cross-group-exchange-diversity/spec.md`: синхронизированные требования.
- `openspec/changes/archive/2026-09-04-diversify-cross-group-exchanges/`: proposal, design, delta specs, завершённые tasks и этот отчёт.

Change архивирован CLI после sync основных specs. Предупреждение архиватора об одном незавершённом пункте относилось только к самому действию архивирования; после подтверждения архива этот пункт закрыт.
