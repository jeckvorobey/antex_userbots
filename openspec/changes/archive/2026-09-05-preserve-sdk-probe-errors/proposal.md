## Why
Review P2: SDK ошибки хранят payload в raw_response; startup теряет whitelisted diagnostics.
## What Changes
- Поддержать SDK raw_response и покрыть настоящим SDK исключением.
## Capabilities
### New Capabilities
Нет.
### Modified Capabilities
- `swarm-runtime`: сохранить безопасные поля ошибки SDK.
## Impact
ai/openrouter_catalog.py и tests/test_openrouter_catalog.py.
