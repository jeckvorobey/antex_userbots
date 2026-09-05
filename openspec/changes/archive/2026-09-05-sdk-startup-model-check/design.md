## Context
Startup использует отдельный HTTP POST и не раскрывает результат проверки оператору.
## Goals / Non-Goals
Общий SDK request builder и один runtime client; видимые проверочные ответы. Telegram сообщения и настройки моделей не меняются.
## Decisions
Выделить общий SDK-вызов в OpenRouterClient. Проверять одну модель через models=[model], не мутируя runtime models. Runtime передаёт существующий клиент со всеми настройками; standalone диагностика создаёт и закрывает свой. Сохранить общий deadline 8 секунд на модель поверх SDK retries. Логировать только короткий проверочный ответ с редактированием ключа и длинных секретов; JSON оставляет text_received.
## Risks / Trade-offs
SDK retry может не успеть за deadline → перейти к следующей модели. Тесты используют fake SDK и MockTransport каталога без внешних запросов.
