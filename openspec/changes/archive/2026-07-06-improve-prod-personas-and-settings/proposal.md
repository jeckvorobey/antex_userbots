## Why

Prod settings and committed bot persona files have drifted: `settings.prod.toml` is not loadable as-is, the configured bot set does not match `.env.prod`, and several production sessions have no persona profile. Existing persona files are too short, so Gemini receives nearly identical identity overlays and the swarm bots sound alike.

## What Changes

- Make `config/settings.prod.toml` syntactically valid and align its `[[swarm.bots]]` entries with the production `SESSION_STRING_*` variables.
- Add missing production persona files and remove persona files that are not referenced by production settings.
- Rewrite every production persona profile with detailed, recognizable character guidance while preserving each character name, role, and original high-level instruction style.
- Add automated checks that validate the production settings file against `.env.prod` key names without exposing secret values.
- Add automated checks that every production persona file is non-trivial, structured, unique, and referenced by production settings.

## Capabilities

### New Capabilities

- `production-personas`: Covers the production persona profile inventory, richness, uniqueness, and alignment with production swarm bot settings.

### Modified Capabilities

- `runtime-configuration`: Production settings must remain valid TOML and resolve all configured production swarm bot sessions from `.env.prod`.
- `prompt-and-gemini`: Persona overlays must provide detailed, distinctive human-style behavior guidance rather than minimal near-identical profiles.

## Impact

- Affected files: `config/settings.prod.toml`, `.env.prod` key compatibility checks, `ai/prompts/bots/*.md`, prompt/config tests, OpenSpec specs, and project documentation.
- No runtime dependencies, database schema, Telegram API behavior, or Gemini SDK behavior change.
- The change affects generated text behavior because persona overlays become richer and more distinct.
