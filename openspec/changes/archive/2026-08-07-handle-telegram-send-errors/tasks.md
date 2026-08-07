## 1. Реализация

- [x] 1.1 Классифицировать permanent Telegram send errors для initiator и responder.
- [x] 1.2 Сохранять initiator/responder draft до Telegram send и использовать его при retry.
- [x] 1.3 При permanent error выключать аккаунт из runtime-пула и переназначать turn доступной персоне.
- [x] 1.4 Помечать exchange `skipped`, если замены нет, и не сохранять history неотправленного сообщения.
- [x] 1.5 Сохранять global quarantine и не запускать отключённый аккаунт после рестарта.
- [x] 1.6 Переназначать persisted exchange с недоступным участником до занятия scheduled slot и до вызова LLM.
- [x] 1.7 Сохранять quarantine и structured log при permanent error в addressed-reply пути.
- [x] 1.8 Не создавать новый exchange, если после quarantine в активном пуле меньше двух ботов.

## 2. Проверка

- [x] 2.1 Добавить regression-тесты permanent/temporary error и persisted responder draft.
- [x] 2.2 Запустить полный test suite.
- [x] 2.4 Добавить regression-тесты для persisted exchange с недоступным участником и отсутствием `KeyError` в scheduled slot.
- [x] 2.5 Добавить regression-тесты persistent quarantine в addressed-reply и защиты pool < 2.
- [x] 2.3 Проверить `openspec validate --strict --all`: CLI отсутствует в окружении, поэтому команда неприменима.
