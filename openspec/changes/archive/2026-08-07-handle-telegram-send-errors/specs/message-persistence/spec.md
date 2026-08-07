## ADDED Requirements

### Requirement: LLM draft переживает повторную попытку Telegram send

Runtime MUST сохранять сгенерированный текст в SQLite до вызова Telegram `send_message`.

#### Scenario: Вопрос инициатора уже сгенерирован

- **WHEN** planned exchange содержит `question_text`
- **THEN** runtime MUST использовать этот текст для send retry
- **AND** MUST NOT снова вызывать `start_topic`

#### Scenario: Ответ responder уже сгенерирован

- **WHEN** started exchange содержит `responder_text`
- **THEN** runtime MUST использовать этот текст для send retry
- **AND** MUST NOT снова вызывать Gemini `generate_reply`

#### Scenario: Отправка успешна

- **WHEN** Telegram подтверждает send
- **THEN** runtime MUST сохранить message history и обновить статус exchange

#### Scenario: Отправка неуспешна

- **WHEN** Telegram send завершается ошибкой
- **THEN** runtime MUST NOT сохранять соответствующее сообщение в history как отправленное
