## Purpose

Определять и логировать право каждого startup-аккаунта отправлять сообщения в подключённую группу.

## Requirements

### Requirement: Логирование права отправки при startup
После получения доступа бота к enabled группе система SHALL определить и записать в лог возможность отправки сообщений этим аккаунтом.

#### Scenario: Права успешно определены
- **WHEN** startup membership check получил entity группы и Telethon возвращает права
- **THEN** лог SHALL содержать `can_write`, `participant_banned_rights.send_messages`, `default_banned_rights.send_messages` и `is_admin` для bot и группы

#### Scenario: Права недоступны
- **WHEN** Telethon не возвращает права или запрос прав завершается ошибкой
- **THEN** система SHALL продолжит startup и запишет диагностическое предупреждение с `can_write=unknown`
