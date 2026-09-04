## Context

The production TOML currently contains two Vietnam groups and a shared UTC+7 schedule of `03-04` and `09-11`. Group configuration is validated as strict TOML, and every group keeps independent routing, history, anti-repeat, and scheduled-exchange state by `id` and `group_chat_id`.

The supplied Telegram values are numeric peer identifiers only. No public username, URL, or private invite link has been provided.

## Goals / Non-Goals

**Goals:**

- Add the three supplied city groups as enabled production entries with stable `group_chat_id` values.
- Express effective UTC windows per city: UTC+7 for Pattaya and Phu Quoc, UTC+4 for Batumi.
- Validate the group inventory and effective schedules without reading or printing production secrets.

**Non-Goals:**

- Do not add a Bangkok group: no peer id or target was supplied, and it is absent from the current production configuration.
- Do not modify the bot roster, prompts, SQLite schema, application code, or Coolify deployment settings.
- Do not add a `group_target`; membership must be established manually for group-id-only entries before production startup.

## Decisions

- Use `peer_id` as `group_chat_id`; it is already in the Telethon-compatible `-100...` form required by the runtime.
- Use stable internal ids `batumi`, `pattaya`, and `phuquoc`; these are independent from visible Telegram titles and scope persisted group history.
- Set explicit group schedule overrides for all added groups. Pattaya and Phu Quoc use `03-04` and `09-11` UTC, matching the existing Vietnam local windows (10:00-11:00 and 16:00-18:00 at UTC+7). Batumi uses `06-07` and `12-14` UTC for the same local windows at UTC+4.
- Keep `group_target` unset rather than inventing usernames from titles. The configuration contract accepts a chat id without a target.

## Risks / Trade-offs

- [A userbot is not already a member of a group-id-only chat] -> Invite every enabled production account before startup; the runtime cannot autojoin without a public target or invite link.
- [Thailand and Vietnam schedule intent was described with "Bangkok", but no Bangkok group data was provided] -> Apply the UTC+7 schedule to supplied Pattaya and Phu Quoc entries only; record the missing Bangkok input explicitly.
- [Local production config is ignored by Git] -> Validate the exact file locally and transfer that file deliberately to the production deployment.
