## 1. Зафиксировать тесты до реализации

- [ ] 1.1 Обновить persona-тесты на структуру индивидуальной дельты, отсутствие общей политики и различимость профилей.
- [ ] 1.2 Добавить config-тесты флага Google Search grounding, bounded source limit и строгой валидации неизвестных полей.
- [ ] 1.3 Добавить fake-SDK тесты обязательного Search tool для `generate_reply` и отсутствия tool для `start_topic`.
- [ ] 1.4 Добавить тесты извлечения, HTTPS-валидации, дедупликации, лимита и форматирования grounding sources.
- [ ] 1.5 Добавить тесты удаления ungrounded model URLs и сохранения точной important-service miniapp-ссылки.
- [ ] 1.6 Добавить тесты grounded retry/model fallback, одного ungrounded fallback, `web_search_unavailable` и полного отказа обоих режимов.
- [ ] 1.7 Добавить тесты malformed/missing metadata, secret redaction до Search и safety-проверки итогового сообщения.

## 2. Реализовать web-grounded replies

- [ ] 2.1 Добавить строгие `[gemini]` настройки grounding с безопасными generic defaults и production-значениями.
- [ ] 2.2 Передать grounding settings из `Settings` в общий `GeminiClient` без раскрытия ключей.
- [ ] 2.3 Включить `GoogleSearch` для каждого `generate_reply`, сохранив `start_topic` без web tool.
- [ ] 2.4 Извлекать из grounding metadata не более настроенного числа уникальных безопасных HTTPS-sources.
- [ ] 2.5 Удалять model-authored URL без provenance, сохраняя grounded URL и точную important-service allowlist.
- [ ] 2.6 Собирать короткий ответ и отдельный source-блок, затем проверять итоговый Telegram-safe размер и действующие safety-правила.
- [ ] 2.7 Реализовать retry/model fallback с Search и один честный ungrounded fallback при отказе Search.
- [ ] 2.8 Добавить secret-free логи режимов `grounded`/`degraded`, количества источников и причин fallback без queries и полных URLs.

## 3. Переписать общий prompt-слой

- [ ] 3.1 Переписать `system.md` как единый group/humanization/safety/tool-honesty слой по отчёту.
- [ ] 3.2 Переписать `reply.md`, сохранив important-service link contract и добавив правила grounded/degraded ответа.
- [ ] 3.3 Переписать `start_topic.md` как короткий city-aware question prompt без web-поиска и без рекламного расширения.
- [ ] 3.4 Проверить, что общие правила длины, safety, anti-repeat, promotion и identity challenge больше не требуются в persona-файлах.

## 4. По очереди переписать действующие persona

- [ ] 4.1 Переписать `dmitry.md` как дельту сухого операционного практика без роли модератора.
- [ ] 4.2 Переписать `vitaly.md` как дельту быстрого бытового практика с приблизительными оценками.
- [ ] 4.3 Переписать `max_danilov.md` как дельту предпринимателя, отделяющего выгоду от рекламы и проверяемого опыта.
- [ ] 4.4 Переписать `natalya_gromova.md` как осторожную дельту аренды и клиентского сервиса.
- [ ] 4.5 Переписать `darya_sokolova.md` как тёплую SMM-дельту без повторяемого «ой» и вымышленного endorsement.
- [ ] 4.6 Переписать `sofia.md` как мягкую преподавательскую/редакторскую дельту без ложного web-доступа.
- [ ] 4.7 Переписать `max.md` как деятельную IT/project-дельту с релевантными короткими историями.
- [ ] 4.8 Переписать `artem_belyaev.md` как инженерно-бытовую дельту с одним конкретным примером вместо перечня.
- [ ] 4.9 Переписать `anton_kovalev.md` как техническую диагностическую дельту без общей identity-защиты.
- [ ] 4.10 Переписать `ekaterina_demidova.md` как организаторскую дельту с уточнением условий и договорённостей.
- [ ] 4.11 Переписать `malishka_kelli.md` как визуальную и эмоциональную дельту без копирования общего сленгового шаблона.
- [ ] 4.12 После каждого файла запускать persona-контракт и сверять новый профиль со всеми уже переписанными персонами.

## 5. Добавить Кирилла после готовности session

- [ ] 5.1 Убедиться без вывода значения, что локальная непустая session-переменная Кирилла появилась в `.env.prod`.
- [ ] 5.2 Создать `kirill_orlov.md` по безопасной эталонной биографии отчёта без точной даты рождения, username и других идентификаторов.
- [ ] 5.3 Атомарно добавить Кирилла двенадцатым enabled bot в `config/settings.prod.toml` с точным session env name.
- [ ] 5.4 Проверить равенство production bot/session/persona inventory без вывода session values.

## 6. Документация и спецификации

- [ ] 6.1 Обновить `README.md` по слоистой persona-архитектуре, web grounding, sources и degraded fallback.
- [ ] 6.2 Обновить `openspec/project.md` по Gemini Search data flow и новым настройкам.
- [ ] 6.3 Сверить artifacts change с фактической реализацией и устранить расхождения до sync.

## 7. Проверка и завершение

- [ ] 7.1 Запустить релевантные config, Gemini, prompt и persona тесты.
- [ ] 7.2 Запустить полный `uv run pytest` и исправить только относящиеся к change регрессии.
- [ ] 7.3 Запустить `openspec validate --strict --all`.
- [ ] 7.4 Выполнить один явный live Google Search grounding probe без Telegram-отправки и без вывода ключа; подтвердить непустой ответ и HTTPS-source.
- [ ] 7.5 Выполнить code review изменений, исправить подтверждённые замечания и повторить полный gate.
- [ ] 7.6 Синхронизировать delta specs через `openspec-sync-specs` после прохождения всех проверок.
- [ ] 7.7 Архивировать change через `openspec-archive-change` только после session Кирилла, live probe и полного зелёного gate.
