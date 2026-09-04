## Context

Important-service scheduled exchanges are selected by the orchestrator and passed to Gemini through prompt context markers. The current context and prompt require `@tt_exchenge_bot`, while README and OpenSpec specs document the same behavior. The requested behavior is a narrower public-copy change: use `https://t.me/tt_exchenge_bot/antex` as the required service contact.

## Goals / Non-Goals

**Goals:**

- Make important-service responder prompts require the miniapp URL.
- Keep the contact value centralized so prompt context, tests, and docs do not drift.
- Preserve existing safety behavior, including blocking private invite links and excessive mentions.

**Non-Goals:**

- Do not change scheduled exchange selection, cooldowns, routing, or persistence.
- Do not add a Telegram preview API or force preview generation; Telegram clients decide whether a public URL gets preview.
- Do not introduce configurable service links in TOML for this small copy change.

## Decisions

- Keep a single `IMPORTANT_SERVICE_CONTACT` constant in `userbot/orchestrator.py`, changing its value to the miniapp URL. This preserves the current architecture and avoids spreading the URL through code.
- Update prompt text to describe the contact as a miniapp link. This keeps generated wording natural while requiring the exact destination.
- Update tests at the prompt/orchestrator boundary rather than mocking Telegram rendering. The behavior contract is the generated prompt/context content, not client preview display.

## Risks / Trade-offs

- Telegram may not show a preview for every `t.me` miniapp URL in every client. Mitigation: use the full URL so Telegram has the best available preview opportunity.
- The output safety validator allows public `https://t.me/...` links except private invite forms. Mitigation: keep existing invite-link blocking tests unchanged and add explicit coverage for the miniapp URL.
