## 1. Реализация

- [x] 1.1 Классифицировать permanent Telegram send errors для initiator и responder.
- [x] 1.2 Сохранять initiator/responder draft до Telegram send и использовать его при retry.
- [x] 1.3 При permanent error выключать аккаунт из runtime-пула и переназначать turn доступной персоне.
- [x] 1.4 Помечать exchange `skipped`, если замены нет, и не сохранять history неотправленного сообщения.
- [x] 1.5 Сохранять group-scoped quarantine и не запускать отключённый аккаунт после рестарта.

## 2. Проверка

- [x] 2.1 Добавить regression-тесты permanent/temporary error и persisted responder draft.
- [x] 2.2 Запустить полный test suite.
- [ ] 2.3 Выполнить `openspec validate --strict --all` при доступном CLI.
