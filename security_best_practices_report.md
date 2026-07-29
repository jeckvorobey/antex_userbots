# Security Best Practices Report

Дата проверки: 2026-07-29

## Executive Summary

Проверен весь актуальный checkout `usbttg`, включая незакоммиченные изменения, Python-код,
runtime-конфигурацию, SQLite, Telegram/LLM boundaries, Git exclusions и locked dependencies.
Проект является Python/Telethon worker без HTTP-сервера. В references навыка нет общего
Python или Telethon профиля, поэтому использованы известные практики Python, Telegram,
SQLite и внешних LLM, а зависимости дополнительно проверены через `pip-audit` и OSV.

Текущий статус:

- Critical: 0
- Open High: 0
- Fixed High: 2
- Accepted Medium: 1
- Accepted Low: 1

По решению пользователя исправлены только SEC-01 и SEC-02. SEC-03 и SEC-04 оставлены без
изменений как принятые риски.

## Fixed High Severity

### SEC-01: Reply allowlist отключался для target-only групп

**Impact:** участник любой другой группы, где состоит userbot, может адресным reply
инициировать обработку сообщения и внешний Gemini-вызов.

**Evidence**

- `run.py:658-661` собирает allowlist только из настроенных числовых `group_chat_id`.
- Если множество пустое, выражение `enabled_group_chat_ids or None` передаёт `None`.
- `userbot/reply_router.py:68` и `userbot/reply_router.py:88-91` трактуют `None` как
  отсутствие фильтра, а не как запрет обработки.
- Разрешённая конфигурация допускает группу только с `group_target`; существующий
  runtime-тест в `tests/test_runtime.py:176-180` использует именно такой вариант.
- Тест `tests/test_reply_router.py:63-78` проверяет отказ только при непустом allowlist и
  не покрывает пустой список разрешённых групп.

**Remediation**

- Router нормализует `None` в пустое множество и всегда отклоняет chat id вне allowlist.
- Runtime больше не преобразует пустое множество в `None`.
- До регистрации handlers target-only группы резолвятся через Telethon, а marked peer id
  добавляется в разделяемый allowlist.
- После reload успешно разрешённые peer id также добавляются в это же множество.
- Добавлены regression-тесты пустого allowlist, target-only startup и marked channel id.

### SEC-02: `uv.lock` содержал зависимости с известными уязвимостями

**Impact:** сетевой worker использует уязвимые криптографические и HTTP-компоненты; наиболее
серьёзные опубликованные advisory допускают удалённый DoS, а остальные затрагивают
валидацию сетевых имён, ASN.1 и обработку redirects/secrets.

**Remediation**

- В `pyproject.toml` добавлены минимальные безопасные runtime constraints.
- `uv.lock` обновлён до `cryptography 49.0.0`, `idna 3.18`, `pyasn1 0.6.4`,
  `urllib3 2.7.0`, `pydantic-settings 2.14.2`.
- `uv sync --extra dev` применил новый lock.
- Повторный `pip-audit` не обнаружил advisory в runtime-пакетах. Остались только advisory
  для `pip 25.2` внутри локального tool environment; `pip` отсутствует в dependency graph
  приложения и `uv.lock`.

## Accepted Medium Severity

### SEC-03: Передача истории во внешний LLM включена по умолчанию

**Impact:** новый runtime без явного privacy-решения отправляет Gemini пользовательское
сообщение и bot-specific историю группы; regex-redaction не является полноценным DLP.

**Evidence**

- `core/config.py:243-244` включает оба внешних LLM gate по умолчанию.
- `userbot/reply_router.py:175-187` загружает историю и передаёт её вместе с сообщением.
- `ai/gemini.py:146-151` формирует внешний prompt из истории и текущего текста.
- `ai/gemini.py:312-317` удаляет только несколько известных форматов секретов.

**Recommendation**

Выбрать явную политику: secure default `false` с обязательным opt-in либо обязательные поля
без defaults в production-конфигурации. Для включённых групп документировать передачу
данных внешнему провайдеру и ограничить объём/возраст отправляемой истории.

**Decision:** не исправлять по указанию пользователя.

## Accepted Low Severity

### SEC-04: Runtime не проверяет права secret-файлов

Текущие `.env` и `.env.prod` имеют `0600`, README требует эти права, а SQLite runtime
сам применяет `0600` (`storage/sqlite_database.py:165-169`). Однако загрузка `.env` в
`core/config.py:341-350` не проверяет владельца и mode. При новом deployment файл,
созданный с permissive `umask`, может остаться доступным другим локальным пользователям.

**Recommendation**

При старте отклонять или как минимум явно предупреждать о `.env`/`.env.prod`, если файл не
принадлежит текущему пользователю или имеет group/other permissions.

**Decision:** не исправлять по указанию пользователя.

## Positive Controls

- `.env*`, локальные TOML, SQLite и Telegram runtime artifacts исключены из Git:
  `.gitignore:23-31`.
- Prompt/persona traversal ограничен до локальных каталогов.
- SQL-значения параметризованы; динамические migration identifiers берутся из внутренних
  констант.
- Нет `eval`, `exec`, `shell=True`, небезопасной pickle/YAML-десериализации или HTTP-сервера.
- Reply path имеет rate limit, pending cap и output safety fallback.
- Private Telegram invite hashes и proxy credentials редактируются в логах.
- SQLite имеет retention cleanup и `0600`.
- `uv lock --check` проходит; lock содержит hashes.

## Verification

- Ручной просмотр всех runtime Python-модулей и конфигурационных границ.
- Поиск secret patterns, command execution, unsafe deserialization, динамического SQL и
  опасных файловых операций.
- `git check-ignore` для `.env`, `.env.prod`, TOML и SQLite.
- `uv lock --check`.
- `uv tree` и обратные dependency chains.
- До обновления `pip-audit` выявил runtime advisory в пяти пакетах.
- После обновления runtime-пакеты чисты; оставшиеся advisory относятся только к `pip`
  tool environment и не входят в `uv.lock`.
