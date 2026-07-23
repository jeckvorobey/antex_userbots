# Security review незакоммиченных изменений — 2026-07-23

## Резюме

Проверены изменения Python runtime, тестов и OpenSpec-артефактов, подготовленные к текущему release. Security-review не выявил утечек секретов или новых опасных interfaces; последующий Codex review обнаружил один high-impact риск смешения Telegram peer namespaces. Finding исправлен до merge и закрыт regression-тестом.

Проект является standalone Python/Telethon-приложением без web-framework, поэтому применимого framework-specific reference в skill `security-best-practices` нет. Проверка выполнена по общим Python security practices и правилам проекта.

## Critical

Не найдено.

## High

### SEC-DIFF-01: Коллизия raw ID пользователя и канала — исправлено

**Impact:** индекс мог вернуть личный user-dialog вместо настроенного канала и направить scheduled сообщение в DM.

**Исправление:** личные диалоги исключены из group-index, raw `entity.id` больше не смешивается с namespace-aware `dialog.id`, а точный marked peer ID имеет приоритет при поиске (`run.py:127`, `run.py:177`). Коллизия покрыта тестом (`tests/test_runtime.py:600`).

## Medium

Не найдено.

## Low

Не найдено.

## Проверенные защитные свойства

- Индекс диалогов формируется только из объектов авторизованного Telethon-клиента и не выполняет внешние строки как код (`run.py:119`, `run.py:156`).
- Кэш разделён по нормализованной идентичности группы и хранится только в памяти клиента (`run.py:221`, `run.py:230`).
- Private invite link не передаётся в `get_entity` и выводится в логах только через redaction (`run.py:274`, `run.py:413`).
- Membership остаётся последовательным; изменение не создаёт параллельный поток join-запросов (`run.py:381`).
- Поиск потенциальных ключей и production session values в будущем коммите не выявил реальных секретов. Совпадение в `tests/test_config_toml.py:457` является синтетической test fixture.

## Проверки

- `uv run pytest` — 201 passed.
- `uv run pytest tests/test_runtime.py tests/test_config_toml.py -q` — 65 passed.
- `openspec validate --strict --all` — 9 passed, 0 failed.
- `git diff --check` — успешно.
