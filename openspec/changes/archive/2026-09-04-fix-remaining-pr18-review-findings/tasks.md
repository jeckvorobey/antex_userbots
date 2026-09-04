## 1. Packaging and boundary validation

- [x] 1.1 Добавить RED-тест wheel import и включить `storage*` в package discovery.
- [x] 1.2 Добавить RED-тесты case-insensitive invite, marked persistence id и совместимых proxy schemes; исправить boundary normalization.

## 2. Persistence and lifecycle

- [x] 2.1 Добавить RED-тест concrete `mark_exchange_skipped` и реализовать terminal transition.
- [x] 2.2 Добавить RED-тесты rollback startup activation и порядка durable quarantine; исправить `SwarmManager`.
- [x] 2.3 Добавить RED-тест OpenRouter close при SDK error и гарантировать закрытие HTTP transport.

## 3. Addressed reply safety

- [x] 3.1 Добавить RED-тесты повторной group/bot eligibility проверки перед publish.
- [x] 3.2 Добавить RED-тест handler-safe disable и отложить физический disconnect.

## 4. Reload and reconnect groups

- [x] 4.1 Добавить RED-тест reload safety limits и обновлять shared generation client.
- [x] 4.2 Добавить RED-тест pending group retry без нового mtime и реализовать desired/ready registry.
- [x] 4.3 Добавить RED-тест reconnect по актуальному набору групп и сделать startup hook динамическим.

## 5. Important service and cooldown

- [x] 5.1 Добавить RED-тесты initiator/responder link contract и one-turn gating.
- [x] 5.2 Перенести scenario instructions в tracked prompt resource и загрузить через PromptLoader с тестами.
- [x] 5.3 Добавить RED-тест cooldown без unsent responder и скорректировать query.

## 6. Documentation and delivery

- [x] 6.1 Обновить README и синхронизировать все delta specs.
- [x] 6.2 Выполнить targeted/full tests, wheel smoke, dependency audit и strict OpenSpec validation.
- [x] 6.3 Архивировать change, commit/push, проверить PR comments/checks и повторить Codex Review.

## 7. Follow-up review findings

- [x] 7.1 Добавить RED-тесты generic credential URI redaction и non-HTTP/scheme-less output links; расширить safety patterns.
- [x] 7.2 Добавить RED-тест общего proxy intersection и синхронизировать Settings с Telethon conversion.
- [x] 7.3 Добавить RED-тест retry после невалидного reload и обновлять mtime только после успешной загрузки.
- [x] 7.4 Добавить RED-тест минимального output cap и запретить значения короче обязательного fallback.
- [x] 7.5 Добавить RED-тест миграции legacy exchange scope и выполнить backfill после resolve первой группы.

## 8. Second follow-up review findings

- [x] 8.1 Добавить RED wheel test для entrypoint и prompt/persona package data; исправить packaging и installed defaults.
- [x] 8.2 Добавить RED-тест отсутствия Python service directives в exchange context и оставить wording/contact в prompt resources.
- [x] 8.3 Добавить RED-тест безопасной ошибки rejected credential proxy и скрыть validation input.
