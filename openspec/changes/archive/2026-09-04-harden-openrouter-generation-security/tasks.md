## 1. Provider Request And Output Policy

- [x] 1.1 Add failing tests for the 256-token request bound, credential-URL redaction, and output URL allowlist
- [x] 1.2 Implement the bounded request, credential-URL redaction, and exact Mini App URL allowlist

## 2. Masked Runtime Secrets

- [x] 2.1 Add failing configuration and runtime tests for masked key/proxy values and constructor unwrapping
- [x] 2.2 Implement SecretStr-backed settings and unwrap values only at OpenRouter and Telethon construction

## 3. Dependency And Documentation

- [x] 3.1 Upgrade cryptography to 50.0.0 or newer and regenerate uv.lock
- [x] 3.2 Update README and the security review report to describe the effective controls and closed findings

## 4. Verification And OpenSpec Closure

- [x] 4.1 Run targeted tests, full pytest, dependency audit, diff checks, and strict OpenSpec validation
- [x] 4.2 Sync delta specs into main specs and archive the completed change
