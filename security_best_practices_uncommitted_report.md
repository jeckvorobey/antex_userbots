# Security Best Practices Report — uncommitted scope

Дата проверки и исправления: 2026-09-04.

## Краткий вывод

Проверены только незакоммиченные файлы текущего checkout `feature/openrouter-provider`:
Python runtime и тесты, конфигурационные шаблоны, зависимости и связанная документация.

Критических и высоких уязвимостей не подтверждено. Все пять найденных рисков
закрыты в текущем worktree без изменения широкого класса допустимых пользовательских
данных: email и телефонные номера намеренно не редактируются общей regex.

## Закрытые находки

### SEC-001: неограниченный размер OpenRouter completion — исправлено

- Каждый Chat Completions request содержит `max_completion_tokens=256`.
- Локальный `max_output_chars` остаётся отдельным post-generation safety gate.
- Request contract закреплён unit-тестом fake SDK.

### SEC-002: произвольные ссылки в AI-ответах — исправлено

- Перед Telegram send разрешён только точный URL `https://t.me/tt_exchenge_bot/antex`.
- Обычные, Markdown и приватные Telegram URL отклоняются общим output safety gate.
- Текст без URL продолжает проходить без изменения.

### SEC-003: уязвимый `cryptography 49.0.0` — исправлено

- Нижняя граница поднята до `cryptography>=50.0.0`.
- `uv.lock` обновлён до `cryptography 50.0.1`.
- Исходный advisory: <https://github.com/pyca/cryptography/security/advisories/GHSA-g6cj-pr64-35w5>.

### SEC-004: credential-bearing URL уходили провайдеру — исправлено

- URL с `userinfo` заменяются на `<redacted_credential_url>` до вызова OpenRouter.
- Общая PII-redaction не вводилась, чтобы не повреждать легитимный текст переписки.
- Существующие `zdr=true` и `data_collection=deny` сохранены.

### SEC-005: provider key и proxy хранились как обычные строки — исправлено

- `OPENROUTER_API_KEY` и `PROXY` представлены через `pydantic.SecretStr`.
- Значения маскируются в `str`/`repr` и раскрываются только на границах создания
  OpenRouter и Telethon клиентов.
- Reload конфигурации сохраняет маскирующий тип.

## Сохранённые защитные меры

- OpenRouter routing требует ZDR endpoints, запрещает сбор данных и требует поддержку параметров.
- Ошибки provider не включают prompt, credentials или исходный exception text в логи.
- Proxy credentials не попадают в логируемое описание соединения.
- Persona-файлы защищены от absolute path и path traversal.
- Приватные Telegram invite links редактируются в runtime-логах.

## Проверка

- Targeted security/config/runtime tests: 138 passed, 1 skipped.
- Полный `uv run pytest`: 293 passed, 1 skipped.
- `uv run --with pip-audit pip-audit`: известных уязвимостей не найдено; локальный
  пакет `tg-userbot` ожидаемо пропущен, потому что отсутствует на PyPI.
- `git diff --check`: успешно.
- `openspec validate --all --strict` после архивирования change: 13 items passed, 0 failed.

## Scope

Коммит, push, PR и deploy не выполнялись. Изменения относятся только к текущему
незакоммиченному checkout и не затрагивают пользовательские секреты или данные.
