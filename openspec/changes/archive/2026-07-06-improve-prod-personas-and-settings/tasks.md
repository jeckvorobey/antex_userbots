## 1. Production Config Tests

- [x] 1.1 Add tests that parse `config/settings.prod.toml` and validate its bot session references against `.env.prod` key names.
- [x] 1.2 Add tests that production persona files exist, are referenced by prod settings, and contain required behavioral sections.

## 2. Production Config Implementation

- [x] 2.1 Fix `config/settings.prod.toml` syntax and align the production bot roster with `SESSION_STRING_*` keys in `.env.prod`.
- [x] 2.2 Ensure each production bot references an existing persona file with a stable `persona_file` path.

## 3. Persona Content

- [x] 3.1 Remove persona files that are not part of the production bot roster.
- [x] 3.2 Expand every retained existing persona profile with detailed, unique personality guidance.
- [x] 3.3 Add missing production persona profiles with the same detailed structure.

## 4. Documentation And Validation

- [x] 4.1 Update OpenSpec main specs and project documentation to describe the production persona/config contract.
- [x] 4.2 Run relevant pytest and OpenSpec validation commands.
- [x] 4.3 Archive the completed OpenSpec change.
