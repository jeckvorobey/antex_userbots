## Context

The runtime loads bot personas from `ai/prompts/bots` through each production bot's `persona_file`. The current profiles are short and mostly identical, while `settings.prod.toml` contains a TOML typo and does not include all `SESSION_STRING_*` entries present in `.env.prod`.

The change is content-heavy but affects runtime behavior because Gemini receives richer persona overlays. It must stay repository-local, avoid logging secrets, and preserve the existing prompt loading architecture.

## Goals / Non-Goals

**Goals:**

- Keep production settings valid and aligned with `.env.prod` key names.
- Keep only production persona files that are referenced by production settings.
- Expand every retained persona into a detailed, distinct Markdown profile.
- Preserve each retained character name, role, and the existing instruction that they write like a living chat participant without mentioning AI/bot identity.
- Add tests that catch invalid production settings, missing persona files, unused production persona files, and too-short/incomplete persona profiles.

**Non-Goals:**

- Do not change Telethon, Gemini, scheduler, database, or prompt-composition code paths.
- Do not change secret values in `.env.prod`.
- Do not invent a large biography or force deterministic responses.
- Do not make personas caricatures, assistants, or advertisements.

## Decisions

- Validate `.env.prod` by key names only. This keeps tests useful for config drift while avoiding secret disclosure in test output.
- Treat `settings.prod.toml` as the source of the production bot roster. The `.env.prod` `SESSION_STRING_*` keys must be represented there, and every configured `persona_file` must exist.
- Remove persona files that are not referenced by production settings. This reduces prompt inventory ambiguity and makes it clear which identities are active.
- Use consistent Markdown section headings across all profiles. The content under each heading remains unique so tests can check structure without dictating exact writing style.
- Keep natural variation as prompt guidance rather than code. This preserves the existing architecture where persona behavior is controlled by prompt files.

## Risks / Trade-offs

- Rich profiles increase prompt size -> Mitigation: keep each profile focused on behavior, not long biographies.
- Tests can only check structural quality, not actual LLM style quality -> Mitigation: include explicit uniqueness and minimum-detail checks plus manual content review in this change.
- Removing unused persona files could surprise local experiments -> Mitigation: scope removal to production prompt inventory requested by the task; tests and examples still use synthetic names where needed.
