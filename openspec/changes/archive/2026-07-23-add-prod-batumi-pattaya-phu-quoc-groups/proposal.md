## Why

Production swarm currently has only Vietnam groups in its local TOML configuration. The Batumi, Pattaya, and Phu Quoc communities must be added with stable Telegram peer ids and schedules aligned to their local time zones.

## What Changes

- Add enabled production group entries for Batumi, Pattaya, and Phu Quoc using the supplied Telegram `peer_id` values as `group_chat_id`.
- Keep Vietnam and Thailand on the existing UTC+7 schedule: `03-04` and `09-11` UTC.
- Give Batumi a UTC+4 override: `06-07` and `12-14` UTC, preserving the same 10:00-11:00 and 16:00-18:00 local activity windows.
- Leave `group_target` unset because no public targets or invite links were supplied.

## Capabilities

### New Capabilities

- `production-group-configuration`: Defines the production group inventory, stable chat identifiers, and effective UTC scheduling policy for city groups.

### Modified Capabilities

- None.

## Impact

- Local ignored production configuration: `config/settings.prod.toml`.
- Production-configuration contract and its validation coverage in `tests/test_config_toml.py`.
- No application code, bot roster, prompt files, database schema, or secrets change.
