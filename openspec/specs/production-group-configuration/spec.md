# Production Group Configuration

## Purpose

Define the production city group inventory, stable Telegram peer identifiers, and UTC schedules used by the swarm instance.

## Requirements

### Requirement: Production city group inventory
The production configuration SHALL contain enabled `batumi`, `pattaya`, and `phuquoc` group entries with the supplied Telegram peer identifiers as `group_chat_id` values and without an invented `group_target`.

#### Scenario: Supplied groups are loaded from production TOML
- **WHEN** `config/settings.prod.toml` is loaded with declared production bot session keys
- **THEN** it exposes enabled groups `batumi` with `-1003846312748`, `pattaya` with `-1003866538293`, and `phuquoc` with `-1003881684490`

### Requirement: Production group UTC schedule alignment
The production configuration SHALL preserve 10:00-11:00 and 16:00-18:00 local scheduled-exchange windows by using `03-04` and `09-11` UTC for UTC+7 Pattaya and Phu Quoc, and `06-07` and `12-14` UTC for UTC+4 Batumi.

#### Scenario: Effective schedules match city time zones
- **WHEN** the added production groups are resolved from TOML
- **THEN** Pattaya and Phu Quoc use `03-04` and `09-11` UTC while Batumi uses `06-07` and `12-14` UTC
