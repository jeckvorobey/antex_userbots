## Context

Runtime поддерживает hot reload настроек, кеширует `SwarmOrchestrator` по effective signature и обрабатывает permanent Telegram restrictions с durable quarantine. Финальное ревью выявило четыре независимые ветки, где кешированное или производное состояние переживает reload, а fallback/error ordering нарушает действующие контракты.

## Goals / Non-Goals

**Goals:**

- Немедленно применять отключение scheduled LLM после reload.
- Удалять группы без восстановления через derived compatibility fields.
- Сохранять разрешённую Mini App ссылку в безопасном important-service fallback.
- Отключать Telegram-ограниченный аккаунт до распространения quarantine persistence error.

**Non-Goals:**

- Менять публичную TOML-схему, SQLite schema или OpenRouter API.
- Менять regular scheduled fallback или политику ручного снятия quarantine.

## Decisions

1. Добавить `allow_external_llm_for_scheduled` в effective orchestrator signature. Динамический getter не выбран, поскольку остальные настройки orchestrator уже применяются пересозданием кешированного экземпляра.
2. Сохранить исходные `group_chat_id`/`group_target` fallback values во внутренних полях `Settings` до `_apply_app_config`; watcher передаёт только их. Производные поля остаются совместимым публичным представлением, но не становятся источником следующего reload.
3. Выбирать fallback по `exchange_kind`: regular сохраняет существующий нейтральный текст, `important_service` получает короткий локальный текст с точным allowlisted URL.
4. При permanent send error сначала отметить bot локально disabled, затем попытаться сохранить quarantine, обязательно вызвать `manager.disable_bot`, и только после этого повторно поднять persistence error. Reassignment выполняется лишь при успешной quarantine-записи.

## Risks / Trade-offs

- [Изменение security gate пересоздаёт orchestrator] → кеш теряется только для затронутой группы и восстанавливается на следующем tick.
- [Quarantine persistence недоступен] → аккаунт отключается в текущем процессе, а ошибка остаётся видимой; durable защита требует восстановления SQLite.
- [Fallback выглядит менее вариативно] → применяется только при отключённом LLM или unsafe output и остаётся коротким.

## Migration Plan

Миграция данных не требуется. После deploy новые правила применяются на следующем settings reload или scheduled tick. Откат — возврат runtime-коммита.

## Open Questions

Нет.
