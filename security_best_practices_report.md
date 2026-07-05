# Security Best Practices Report

## Executive Summary

Проверка `usbttg` показала, что базовая гигиена на уровне конфигов и SQL в проекте в целом неплохая: есть валидация `persona_file`, секреты вынесены в `.env`, SQL-запросы параметризованы, proxy credentials не логируются напрямую. Основные риски сосредоточены не в классических web-уязвимостях, а в границе между Telegram-группами, локальным persisted history и внешним Gemini API.

Ключевые проблемы:
- любой пользователь в разрешённой группе может без rate limit инициировать дорогой внешний LLM-вызов;
- содержимое групповых диалогов и bot-specific history отправляется во внешний AI-провайдер без слоя минимизации/редакции данных;
- ответы модели публикуются в Telegram без safety gate;
- история диалогов сохраняется в plaintext SQLite без retention policy.

## High Severity

### SEC-01: Неконтролируемая передача содержимого чатов и истории во внешний LLM

**Impact:** любой reply в разрешённой группе приводит к отправке пользовательского текста и bot-scoped истории диалога во внешний Gemini API, что создаёт риск утечки персональных данных, внутренних деталей групп и чувствительного контента.

**Evidence**
- [userbot/reply_router.py](/home/serg/Develop/usbttg/userbot/reply_router.py:91) загружает bot-specific историю чата через `get_session_history(...)`.
- [userbot/reply_router.py](/home/serg/Develop/usbttg/userbot/reply_router.py:97) передаёт `history` и `user_message` в `gemini_client.generate_reply(...)`.
- [userbot/orchestrator.py](/home/serg/Develop/usbttg/userbot/orchestrator.py:460) загружает историю scheduled exchange для responder-а.
- [userbot/orchestrator.py](/home/serg/Develop/usbttg/userbot/orchestrator.py:464) передаёт историю и вопрос в Gemini.
- [ai/gemini.py](/home/serg/Develop/usbttg/ai/gemini.py:121) собирает prompt из истории и пользовательского сообщения.
- [ai/gemini.py](/home/serg/Develop/usbttg/ai/gemini.py:164) отправляет итоговый prompt во внешний SDK вызовом `client.models.generate_content(...)`.
- [run.py](/home/serg/Develop/usbttg/run.py:426) создаёт единый `GeminiClient` для runtime.

**Why this matters**
- в текущем виде нет механизма data minimization перед внешней отправкой;
- нет отдельного режима для групп, где запрещено отдавать контент внешнему провайдеру;
- persisted history расширяет объём данных, уходящих за пределы Telegram.

**Recommendation**
- добавить явный privacy toggle на группу или весь runtime: `allow_external_llm_for_replies`, `allow_external_llm_for_scheduled`;
- перед отправкой в Gemini пропускать историю через sanitizer/redactor;
- ограничить глубину истории для reply path более жёстко, чем “всё доступное по bot_id”.

### SEC-02: Отсутствует anti-abuse/rate limit на публичный reply path

**Impact:** любой участник разрешённой группы может многократно триггерить внешние LLM-вызовы, что создаёт риск cost abuse, деградации сервиса и блокировок со стороны внешнего API.

**Evidence**
- [userbot/reply_router.py](/home/serg/Develop/usbttg/userbot/reply_router.py:40) принимает любое событие из enabled group.
- [userbot/reply_router.py](/home/serg/Develop/usbttg/userbot/reply_router.py:47) фильтрует только swarm users и Telegram-ботов, но не лимитирует обычных участников.
- [userbot/reply_router.py](/home/serg/Develop/usbttg/userbot/reply_router.py:79) при наличии `manager` лишь сериализует доступ через `human_slot`, но не ограничивает частоту.
- [userbot/reply_router.py](/home/serg/Develop/usbttg/userbot/reply_router.py:97) каждый валидный reply уходит в Gemini.

**Why this matters**
- `human_slot` решает только гонки между scheduled и human flows, но не защищает от spam/flood;
- при публичной группе attacker может с одного аккаунта или небольшой фермы reply-ить боту до исчерпания лимитов и бюджета API.

**Recommendation**
- добавить per-user и per-chat rate limiting;
- ввести cooldown на один `reply_to_message_id` или на `(sender_id, bot_id)` окно времени;
- логировать и отбрасывать burst patterns до вызова Gemini.

## Medium Severity

### SEC-03: Публикация model output без safety gate

**Impact:** ответ модели публикуется в группу напрямую, поэтому prompt injection, jailbreak или просто неудачная генерация могут привести к публикации нежелательного, вводящего в заблуждение или разглашающего текста от имени userbot.

**Evidence**
- [userbot/reply_router.py](/home/serg/Develop/usbttg/userbot/reply_router.py:97) получает `response_text` из Gemini.
- [userbot/reply_router.py](/home/serg/Develop/usbttg/userbot/reply_router.py:112) сразу публикует ответ через `event.reply(response_text)`.
- [userbot/orchestrator.py](/home/serg/Develop/usbttg/userbot/orchestrator.py:374) получает `initiator_text` из LLM path.
- [userbot/orchestrator.py](/home/serg/Develop/usbttg/userbot/orchestrator.py:381) сразу отправляет `initiator_text` в группу.
- [userbot/orchestrator.py](/home/serg/Develop/usbttg/userbot/orchestrator.py:464) получает `responder_text` из Gemini.
- [userbot/orchestrator.py](/home/serg/Develop/usbttg/userbot/orchestrator.py:472) сразу публикует `responder_text`.

**Why this matters**
- отсутствует пост-обработка на mentions, ссылки, запрещённые токены, длину, повторение system-style markers;
- модель может быть принуждена к публикации нежелательного текста через контекст переписки.

**Recommendation**
- добавить output policy layer: max length, forbidden patterns, mention allowlist, optional markdown/html sanitization;
- для scheduled exchange ввести safe fallback phrase, если ответ модели не проходит policy;
- отдельно логировать причины block/drop model output.

### SEC-04: Persisted history хранится в plaintext без retention policy

**Impact:** при компрометации хоста, резервных копий или локального доступа злоумышленник получит накопленную историю пользовательских и модельных сообщений без ограничений по сроку хранения.

**Evidence**
- [core/config.py](/home/serg/Develop/usbttg/core/config.py:305) задаёт дефолтный путь `data/history.db`.
- [run.py](/home/serg/Develop/usbttg/run.py:422) инициализирует `MessageHistory(settings.db_path)`.
- [run.py](/home/serg/Develop/usbttg/run.py:440) использует тот же путь для `ExchangeStore`.
- [ai/history.py](/home/serg/Develop/usbttg/ai/history.py:35) создаёт постоянную таблицу `messages`.
- [ai/history.py](/home/serg/Develop/usbttg/ai/history.py:65) сохраняет каждое сообщение целиком в поле `text`.

**Why this matters**
- в текущем snapshot нет TTL/purge job, no encryption-at-rest layer и нет отдельного ограничения на хранение чувствительных group messages;
- для userbot, который отправляет эти же данные в LLM, history.db становится концентратором чувствительного контента.

**Recommendation**
- добавить retention policy для `messages` и `scheduled_exchanges`;
- документировать требования к файловым правам на `data/`;
- рассмотреть опциональный режим минимального хранения: только необходимые поля или укороченный history window.

## Positive Controls

- [core/config.py](/home/serg/Develop/usbttg/core/config.py:346) отделяет секретные параметры от TOML-конфига и не требует хранить их в репозитории.
- [ai/gemini.py](/home/serg/Develop/usbttg/ai/gemini.py:268) редактирует proxy description, не выводя credentials напрямую.
- [ai/prompt_composer.py](/home/serg/Develop/usbttg/ai/prompt_composer.py:61) и [core/config.py](/home/serg/Develop/usbttg/core/config.py:288) ограничивают `persona_file` относительным путём внутри профилей.
- [ai/history.py](/home/serg/Develop/usbttg/ai/history.py:93) использует параметризованные SQL-вставки, а не строковую конкатенацию пользовательского текста.

## Suggested Fix Order

1. Закрыть `SEC-02` через rate limiting и abuse guard до вызова Gemini.
2. Закрыть `SEC-03` через output policy layer перед публикацией в Telegram.
3. Закрыть `SEC-01` через data minimization/redaction и group-level privacy toggles.
4. Закрыть `SEC-04` через retention/purge и операционные требования к хранению `history.db`.
