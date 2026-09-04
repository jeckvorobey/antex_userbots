## 1. Regression tests

- [x] 1.1 Добавить RED-тест повторного reconnect после временной ошибки replacement-клиента.
- [x] 1.2 Добавить RED-тест выбора актуального активного клиента scheduler tick-ом и безопасного пропуска без active pool.

## 2. Runtime fixes

- [x] 2.1 Сделать остановку предыдущего клиента при reconnect безопасной при отсутствии записи.
- [x] 2.2 Выбирать актуальный активный Telegram-клиент в начале каждого scheduler tick.

## 3. Documentation and verification

- [x] 3.1 Обновить README и синхронизировать delta spec с основной спецификацией.
- [x] 3.2 Выполнить targeted и полный набор тестов, security audit и строгую OpenSpec-валидацию.
- [x] 3.3 Архивировать завершённый OpenSpec change.
