## Design

Telegram не предоставляет dry-run для отправки сообщения произвольному получателю: возможность писать в конкретный чат зависит также от прав чата и privacy-настроек получателя. Поэтому проверяется только глобальная пригодность аккаунта без публикации контента.

После подключения `UserBotClient` вызывает `messages.setTyping` для `InputPeerSelf` (Saved Messages). Это использует messaging API, но не создаёт сообщение и не затрагивает целевые группы. Только подтверждённые ошибки деактивированного аккаунта, отозванной сессии или глобальной блокировки превращаются в `AccountMessagingUnavailableError`; ошибки отдельного peer не являются global quarantine.

`SwarmManager` ловит это исключение до active-pool registration, останавливает клиента и меняет runtime status на `disabled`. Startup hook сохраняет global quarantine в SQLite; при следующем запуске существующая загрузка quarantined bot ids исключает профиль до создания клиента.
