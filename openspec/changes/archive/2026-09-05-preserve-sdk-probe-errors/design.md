## Context
SDK использует raw_response вместо response.
## Goals / Non-Goals
Сохранить прежнюю диагностику без raw body или свободного текста ошибки.
## Decisions
Fallback на raw_response только при отсутствии response; whitelist и редактирование остаются.
## Risks / Trade-offs
Payload может быть некорректным; существующий безопасный parser сохраняется.
