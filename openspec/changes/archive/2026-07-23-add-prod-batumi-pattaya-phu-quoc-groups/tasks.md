## 1. Production group configuration

- [x] 1.1 Add a regression test for the supplied production group ids and effective UTC schedules.
- [x] 1.2 Add enabled Batumi, Pattaya, and Phu Quoc entries with explicit timezone-aligned schedule overrides to `config/settings.prod.toml`.

## 2. Verification

- [x] 2.1 Validate the production TOML through strict `Settings` loading without exposing secret values.
- [x] 2.2 Run the relevant production configuration tests and strict OpenSpec validation.
