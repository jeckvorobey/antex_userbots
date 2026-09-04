# Replace Gemini with OpenRouter Implementation Plan

> **For agentic workers:** Follow each checkbox in order with test-first RED/GREEN evidence. Work in the current checkout; do not create a worktree or commit/push/PR.

**Goal:** Replace Gemini completely with a provider-neutral generation boundary backed by strict-ZDR OpenRouter Chat Completions.

**Architecture:** `ai/generation.py` owns contracts and safety, `ai/prompt_loader.py` owns prompt files, and `ai/openrouter.py` adapts the official async SDK. Runtime injects one shared `ai_client` into Telegram flows and closes it with the shared SQLite lifecycle.

**Tech Stack:** Python 3.11+, Pydantic Settings, OpenRouter Python SDK, HTTPX async proxy transport, pytest/pytest-asyncio, OpenSpec.

**Spec:** `openspec/changes/replace-gemini-with-openrouter/design.md` and delta specs under `openspec/changes/replace-gemini-with-openrouter/specs/`.

## 1. Strict configuration contract

- [x] 1.1 Update `tests/test_config.py` and `tests/test_config_toml.py` first for required `OPENROUTER_API_KEY`, optional `PROXY`, removal of legacy names, mandatory ordered models, duplicate/blank/model-count validation, optional temperature, fixed timeout/retry settings, and reload preservation; run the focused tests and observe expected RED failures.
- [x] 1.2 Replace `Secrets`/`GeminiConfig` and public settings fields in `core/config.py` with strict OpenRouter equivalents; run `uv run pytest tests/test_config.py tests/test_config_toml.py -q` and mark GREEN only when all pass.

## 2. Provider-neutral generation and OpenRouter adapter

- [x] 2.1 Split existing tests into `tests/test_prompt_loader.py`, `tests/test_generation.py`, and `tests/test_openrouter.py`; cover cached prompt loading, redaction/output safety, exact messages/models/ZDR provider policy, optional temperature omission, timeout/retry configuration, proxy transport, response parsing, error classification, safe logging, and idempotent close; run them and observe RED before implementation.
- [x] 2.2 Create `ai/prompt_loader.py`, `ai/generation.py`, and `ai/openrouter.py` with `TextGenerationClient`, `GenerationError`, `TemporaryGenerationError`, `PromptLoader`, and `OpenRouterClient`; run the three focused test files to GREEN.
- [x] 2.3 Delete `ai/gemini.py` and `tests/test_gemini.py` after all retained behavior has moved; confirm `rg -n 'Gemini|gemini' ai tests --glob '!tests/test_personas.py'` finds no runtime/test dependency.

## 3. Runtime and Telegram wiring

- [x] 3.1 Update runtime, reply-router, and orchestrator tests first to expect `ai_client`, shared `PROXY`, one OpenRouter instance, managed shutdown, reload behavior, and unchanged safety fallback/scheduled flows; run focused tests and observe RED.
- [x] 3.2 Rename `gemini_client` to `ai_client` in `run.py`, `userbot/reply_router.py`, `userbot/orchestrator.py`, and affected runtime models; build/close `OpenRouterClient`, pass the shared proxy to OpenRouter and Telethon, preserve generation method calls, and run `tests/test_runtime.py tests/test_reply_router.py tests/test_orchestrator.py tests/test_swarm_manager.py` to GREEN.

## 4. Dependencies, examples, and documentation

- [x] 4.1 Replace `google-genai` with `openrouter>=1.1.122,<2` and `httpx[socks]>=0.28,<1` in `pyproject.toml`, regenerate `uv.lock`, and verify imports in the locked environment.
- [x] 4.2 Update `.env.example` and `config/settings.example.toml` to the new key/proxy/OpenRouter model contract without real credentials or selected production model slugs.
- [x] 4.3 Update `README.md`, `AGENTS.md`, and `openspec/project.md` for OpenRouter architecture, setup, privacy routing, proxy, tests, limitations, and deferred live verification; leave local `.env*`, production settings, reports, `.superdesign/`, `.gitignore`, and `humanize-production-personas` unchanged.

## 5. Verification and review

- [x] 5.1 Run `uv run pytest` and resolve any regression through a failing focused test before rerunning the full suite.
- [x] 5.2 Map every delta-spec scenario to code/test/documentation evidence, run `rg` checks for removed runtime Gemini/legacy config names, and review the complete diff for secret leakage, raw exception logging, scope drift, lifecycle errors, and user-file changes.
- [x] 5.3 Run `openspec validate --strict --all` and confirm the selected change is apply-complete.

## 6. OpenSpec closure

- [x] 6.1 Sync only `replace-gemini-with-openrouter` deltas into main specs, remove the superseded `openspec/specs/prompt-and-gemini/spec.md`, create `openspec/specs/prompt-and-generation/spec.md`, and validate strictly.
- [x] 6.2 Archive only `replace-gemini-with-openrouter`, validate the archived project, and confirm `humanize-production-personas` remains active and unchanged.

## Deferred operator verification

After repository closure, the operator will supply a real OpenRouter key, at least two model slugs, and two new Telethon sessions. Live acceptance then consists of one non-Telegram probe plus one addressed reply and one scheduled A-to-B exchange; these external prerequisites are not repository implementation tasks and must not expose prompts, output, URLs, credentials, or raw errors.
