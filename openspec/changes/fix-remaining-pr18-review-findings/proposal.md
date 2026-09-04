## Why

GitHub Codex Review подтвердил оставшиеся дефекты упаковки, lifecycle, reload, scheduled exchange и addressed reply, которые могут ломать установленный пакет, терять quarantine, отправлять сообщения после отключения группы или оставлять enabled-группы неактивными после временной ошибки. Все actionable замечания PR #18 должны быть закрыты до merge в `dev`.

## What Changes

- Включить `storage` в дистрибутив и нормализовать Telegram peer/invite/proxy boundaries.
- Сделать startup/quarantine/close lifecycle fail-safe и устранить вызов отсутствующего persistence-метода.
- Повторно проверять eligibility перед отложенной отправкой и безопасно откладывать физический disconnect из event handler.
- Применять reload security limits, сохранять pending-группы для повторной проверки и проверять reconnect-клиенты по актуальному набору групп.
- Перенести important-service инструкции из Python в prompt-файлы, обеспечить обязательный responder turn и контракт ссылки.
- Исключить несостоявшиеся responder turns из cooldown history.
- Добавить regression-тесты, обновить документацию и спецификации.

## Capabilities

### New Capabilities

Нет.

### Modified Capabilities

- `runtime-configuration`: общий proxy поддерживает только схемы, совместимые с Telegram и HTTPX, а reload применяет safety limits.
- `swarm-runtime`: startup/reconnect/reload lifecycle использует актуальные группы, retry pending-групп и fail-safe cleanup.
- `addressed-reply-routing`: eligibility повторно проверяется перед publish, а runtime-disable не прерывает текущий handler.
- `scheduled-exchanges`: important-service exchange всегда включает responder, соблюдает link contract и корректный cooldown.
- `prompt-and-generation`: important-service инструкции загружаются из файлов, OpenRouter transport закрывается даже при SDK error.
- `message-persistence`: skipped exchanges и marked Telegram chat id сохраняются согласованно.

## Impact

Затрагиваются `pyproject.toml`, `run.py`, `core/config.py`, `ai/openrouter.py`, prompt-файлы, `userbot/*`, SQLite queries, tests, README и соответствующие OpenSpec capabilities. В schema БД идемпотентно добавляется поле факта отправки responder-а; формат TOML не меняется, а `socks4://` становится явно недопустимой общей proxy-схемой.
