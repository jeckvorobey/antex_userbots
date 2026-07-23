# Security review незакоммиченных изменений — 2026-07-23

## Резюме

Проверены изменения Python runtime, тестов и OpenSpec-артефактов, подготовленные к текущему release. Security-review не выявил утечек секретов или новых опасных interfaces; последующий Codex review обнаружил один high-impact риск смешения Telegram peer namespaces. Finding исправлен до merge и закрыт regression-тестом.

Проект является standalone Python/Telethon-приложением без web-framework, поэтому применимого framework-specific reference в skill `security-best-practices` нет. Проверка выполнена по общим Python security practices и правилам проекта.

## Critical

Не найдено.

## High

### SEC-DIFF-01: Коллизия raw ID пользователя и канала — исправлено

**Impact:** индекс мог вернуть личный user-dialog вместо настроенного канала и направить scheduled сообщение в DM.

**Исправление:** личные диалоги исключены из group-index, raw `entity.id` больше не смешивается с namespace-aware `dialog.id`, а точный marked peer ID имеет приоритет при поиске (`run.py:128`, `run.py:178`). Коллизия покрыта тестом (`tests/test_runtime.py:600`).

### SEC-DIFF-02: Positive raw ID basic group мог попасть в user namespace — исправлено

**Impact:** ID-only конфигурация legacy/basic group могла не найти marked peer `-id` и передать положительный integer как user peer.

**Исправление:** для положительного raw ID индексный lookup проверяет обе Telegram marked формы: `-id` для basic chat и `-100...` для channel (`run.py:70`). Поведение покрыто collision-тестом (`tests/test_runtime.py:638`).

### SEC-DIFF-03: Неопределённый порядок basic-chat и channel fallback — исправлено

**Impact:** использование `set` не гарантировало порядок marked peer IDs и при общей raw-части могло выбрать channel вместо basic group.

**Исправление:** candidate peer IDs преобразованы в упорядоченную последовательность с приоритетом exact ID, basic-chat `-id`, затем channel `-100...` (`run.py:68`, `run.py:186`). Regression-тест одновременно моделирует basic group, channel и user с одной raw-частью ID (`tests/test_runtime.py:638`).

## Medium

### SEC-DIFF-04: Update-контейнер без chat мог кэшироваться как peer — исправлено

**Impact:** валидный join-ответ типа `UpdatesTooLong` мог попасть в target cache вместо Telegram entity и сломать последующую отправку.

**Исправление:** extractor принимает только chat из `chats` или объект с явным entity ID; update-контейнер без entity возвращает `None` и запускает повторный dialog scan (`run.py:211`, `run.py:342`). Поведение закрыто regression-тестом (`tests/test_runtime.py:728`).

## Low

Не найдено.

## Проверенные защитные свойства

- Индекс диалогов формируется только из объектов авторизованного Telethon-клиента и не выполняет внешние строки как код (`run.py:119`, `run.py:156`).
- Кэш разделён по нормализованной идентичности группы и хранится только в памяти клиента (`run.py:221`, `run.py:230`).
- Private invite link не передаётся в `get_entity` и выводится в логах только через redaction (`run.py:274`, `run.py:413`).
- Membership остаётся последовательным; изменение не создаёт параллельный поток join-запросов (`run.py:381`).
- Поиск потенциальных ключей и production session values в будущем коммите не выявил реальных секретов. Совпадение в `tests/test_config_toml.py:457` является синтетической test fixture.

## Проверки

- `uv run pytest` — 204 passed.
- `uv run pytest tests/test_runtime.py tests/test_config_toml.py -q` — 68 passed.
- `openspec validate --strict --all` — 9 passed, 0 failed.
- `git diff --check` — успешно.
