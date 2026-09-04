## Purpose

Сохранять выбор ботов для scheduled exchange линейным относительно roster и cooldown history.

## Requirements

### Requirement: Линейный выбор кандидатов
Система SHALL выбирать кандидатов для scheduled exchange за один проход roster после обработки recent history prefix.

#### Scenario: Ослабление cooldown
- **WHEN** максимальный cooldown оставляет меньше двух кандидатов
- **THEN** система SHALL сохранить порядок roster и вернёт кандидатов для первого меньшего cooldown, оставляющего минимум двух ботов
