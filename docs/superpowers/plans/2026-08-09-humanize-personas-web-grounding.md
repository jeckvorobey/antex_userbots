# Humanized Personas and Web-Grounded Replies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перевести общий prompt/persona-слой на различимые биографические дельты и дать каждому сгенерированному ответу Google Search grounding с проверенными ссылками и безопасным ungrounded fallback.

**Architecture:** `system.md` становится единственным общим humanization/safety/tool-honesty слоем, а `reply.md`, `start_topic.md` и persona-файлы содержат только сценарные и индивидуальные инструкции. `GeminiClient.generate_reply` включает `GoogleSearch`, извлекает provenance URL из `grounding_metadata`, очищает model-authored URL и при полном отказе grounded-попыток делает один честный запрос без tools; `start_topic` остаётся без поиска.

**Tech Stack:** Python 3.11+, `google-genai 1.70.0`, Pydantic Settings/TOML, Telethon, pytest/pytest-asyncio, OpenSpec.

## Global Constraints

- Сначала тест, затем минимальная реализация; Gemini и Telethon в unit-тестах только fake/stub.
- Все сетевые и DB-интерфейсы остаются async; синхронный SDK-вызов продолжает выполняться через `asyncio.to_thread`.
- Не логировать и не коммитить `GEMINI_API_KEY`, `SESSION_STRING_*`, search queries, полные source URL и private invite hashes.
- Google Search включается для каждого `generate_reply`, но не для `start_topic`.
- Публиковать максимум два уникальных HTTPS-source из `grounding_metadata`; не придумывать source при отсутствии metadata.
- Разрешённый URL без grounding provenance: только точный `https://t.me/tt_exchenge_bot/antex` в important-service ответе.
- При отказе Search сначала выполнить действующие retry и model fallback с tool, затем не более одного ungrounded запроса с маркером `web_search_unavailable`.
- Prompt-only scope не заявляет runtime-гарантии `no_response`, human grace, one-bot cap или clan semantic dedupe.
- Persona Кирилла активируется атомарно только после появления локального session env name; значение session не читает и не создаёт агент.
- После реализации обновить README, `openspec/project.md`, синхронизировать specs и архивировать change только после полного gate и live probe.

---

## File Structure

- `core/config.py` — строгие non-secret grounding settings и публичные runtime-поля.
- `run.py` — передача grounding settings в единый `GeminiClient`.
- `ai/gemini.py` — tool config, grounded response parsing, URL provenance, degraded fallback и safety финального сообщения.
- `ai/prompts/system.md` — общие правила группы, factuality, untrusted input, Search и identity challenge.
- `ai/prompts/reply.md` — правила одного ответа, important-service и degraded режима.
- `ai/prompts/start_topic.md` — короткий city-aware вопрос без web tool.
- `ai/prompts/bots/*.md` — только индивидуальные биографические дельты.
- `tests/test_config.py`, `tests/test_config_toml.py` — defaults, overrides и strict validation.
- `tests/test_gemini.py` — fake SDK tests для tool, metadata, sources, URL safety, retry и fallback.
- `tests/test_runtime.py` — wiring новых settings в общий Gemini client.
- `README.md`, `openspec/project.md` — operator и architecture contracts.
- `config/settings.example.toml`, `config/settings.toml`, локальный `config/settings.prod.toml` — documented/default/production grounding policy.

### Task 1: Grounding Configuration Contract

**Files:**
- Modify: `tests/test_config.py`
- Modify: `tests/test_config_toml.py`
- Modify: `core/config.py`
- Modify: `config/settings.example.toml`
- Modify: `config/settings.toml`
- Modify locally: `config/settings.prod.toml`

**Interfaces:**
- Produces: `Settings.gemini_google_search_grounding_enabled: bool`
- Produces: `Settings.gemini_google_search_max_sources: int`
- Produces: `GeminiConfig.google_search_grounding_enabled: bool = False`
- Produces: `GeminiConfig.google_search_max_sources: int` constrained to `0..5`, default `2`

- [ ] **Step 1: Add failing defaults and override tests**

Add assertions to `test_settings_loads_non_secret_values_from_minimal_toml` and `tests/test_config.py` default coverage:

```python
assert settings.gemini_google_search_grounding_enabled is False
assert settings.gemini_google_search_max_sources == 2
```

Add a TOML override test:

```python
def test_settings_loads_google_search_grounding_config(tmp_path):
    settings_path = write_settings(tmp_path, """
    [gemini]
    google_search_grounding_enabled = true
    google_search_max_sources = 1

    [[swarm.bots]]
    id = "anna"
    session_env = "SESSION_STRING_ANNA"
    persona_file = "anna.md"
    """)
    with patch.dict("os.environ", {"SESSION_STRING_ANNA": "anna-session"}, clear=False):
        settings = Settings(**BASE_SECRETS, settings_path=str(settings_path))
    assert settings.gemini_google_search_grounding_enabled is True
    assert settings.gemini_google_search_max_sources == 1
```

- [ ] **Step 2: Add failing bounds tests**

Parameterize `google_search_max_sources` with `-1` and `6`; assert `Settings` raises validation error. Add `google_search_enabled = true` as a misspelled-field case and assert strict validation rejects it.

- [ ] **Step 3: Run configuration tests and confirm RED**

Run:

```bash
uv run pytest tests/test_config.py tests/test_config_toml.py -q
```

Expected: failures because the new Gemini fields and public settings do not exist.

- [ ] **Step 4: Implement strict config fields**

Extend `GeminiConfig`:

```python
google_search_grounding_enabled: bool = False
google_search_max_sources: int = Field(default=2, ge=0, le=5)
```

In `_apply_app_config`, assign:

```python
self.gemini_google_search_grounding_enabled = config.gemini.google_search_grounding_enabled
self.gemini_google_search_max_sources = config.gemini.google_search_max_sources
```

Document both keys in `config/settings.example.toml`; enable grounding with maximum `2` sources in `config/settings.toml` and local `config/settings.prod.toml`.

- [ ] **Step 5: Run configuration tests and confirm GREEN**

Run the Step 3 command. Expected: all selected tests pass.

- [ ] **Step 6: Commit the configuration contract**

Stage only tracked config/test files; keep ignored `config/settings.prod.toml` local:

```bash
git add core/config.py config/settings.example.toml config/settings.toml tests/test_config.py tests/test_config_toml.py
git commit -m "Добавь настройки Google Search grounding"
```

### Task 2: Runtime Wiring and Search Tool Selection

**Files:**
- Modify: `tests/test_runtime.py`
- Modify: `tests/test_gemini.py`
- Modify: `run.py`
- Modify: `ai/gemini.py`

**Interfaces:**
- Consumes: `Settings.gemini_google_search_grounding_enabled`, `Settings.gemini_google_search_max_sources`
- Produces constructor parameters: `google_search_grounding_enabled: bool = False`, `google_search_max_sources: int = 2`
- Produces internal call: `_generate_text(system_prompt: str, prompt: str, *, use_google_search: bool, allow_ungrounded_fallback: bool) -> str`

- [ ] **Step 1: Write failing runtime-wiring test**

Patch `run.GeminiClient` in the existing `_build_runtime_context` test and assert its kwargs include:

```python
assert captured_kwargs["google_search_grounding_enabled"] is True
assert captured_kwargs["google_search_max_sources"] == 2
```

- [ ] **Step 2: Write failing tool-selection tests**

Extend the fake `types` module with:

```python
class FakeGoogleSearch: ...

class FakeTool:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
```

Create `test_gemini_client_generate_reply_uses_google_search` and assert `config.kwargs["tools"]` contains one `FakeTool` whose `google_search` is `FakeGoogleSearch`. Create `test_gemini_client_start_topic_does_not_use_google_search` and assert `tools` is absent or empty.

- [ ] **Step 3: Run focused tests and confirm RED**

```bash
uv run pytest tests/test_runtime.py tests/test_gemini.py::test_gemini_client_generate_reply_uses_google_search tests/test_gemini.py::test_gemini_client_start_topic_does_not_use_google_search -q
```

Expected: new constructor kwargs/tool assertions fail.

- [ ] **Step 4: Wire settings and build call-specific configs**

Pass the two settings from `run._build_runtime_context`. Store bounded values in `GeminiClient.__init__`:

```python
self.google_search_grounding_enabled = bool(google_search_grounding_enabled)
self.google_search_max_sources = min(5, max(0, google_search_max_sources))
```

Build `GenerateContentConfig` per `_generate_text` call. When `use_google_search` is true:

```python
grounding_tool = types_module.Tool(google_search=types_module.GoogleSearch())
config = types_module.GenerateContentConfig(
    system_instruction=system_prompt,
    temperature=self.temperature,
    tools=[grounding_tool],
)
```

Call with Search from `generate_reply`; call without Search from `start_topic`.

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run the Step 3 command. Expected: pass.

- [ ] **Step 6: Commit runtime wiring**

```bash
git add ai/gemini.py run.py tests/test_gemini.py tests/test_runtime.py
git commit -m "Подключи Google Search к ответам Gemini"
```

### Task 3: Grounding Sources and URL Provenance

**Files:**
- Modify: `tests/test_gemini.py`
- Modify: `ai/gemini.py`

**Interfaces:**
- Produces: `_extract_grounding_sources(response: Any) -> tuple[str, ...]`
- Produces: `_validate_grounding_url(value: object) -> str | None`
- Produces: `_remove_unverified_urls(text: str, allowed_urls: set[str]) -> str`
- Produces: `_format_grounded_reply(text: str, sources: tuple[str, ...]) -> str`
- Constant: `IMPORTANT_SERVICE_URL = "https://t.me/tt_exchenge_bot/antex"`

- [ ] **Step 1: Write failing happy-path metadata test**

Build a fake response with:

```python
grounding_metadata=SimpleNamespace(
    grounding_chunks=[
        SimpleNamespace(web=SimpleNamespace(uri="https://example.com/a", title="A")),
        SimpleNamespace(web=SimpleNamespace(uri="https://example.com/b", title="B")),
    ]
)
```

Assert returned text is:

```text
Короткий ответ.

Источники:
https://example.com/a
https://example.com/b
```

- [ ] **Step 2: Write failing validation and dedupe tests**

Cover duplicate URL, `http://`, embedded credentials, malformed URI, private `t.me/+...`, more than two chunks, missing candidates, missing metadata, `None` web and malformed chunk objects. Assert malformed metadata preserves `response.text` without raising.

- [ ] **Step 3: Write failing model-authored URL tests**

Assert:

- `https://made-up.example/path` is removed when absent from metadata;
- a matching grounded URL remains once and is not repeated in the source block;
- `https://t.me/tt_exchenge_bot/antex` remains even without grounding metadata;
- surrounding sentence spacing and punctuation remain readable after removal.

- [ ] **Step 4: Run source tests and confirm RED**

```bash
uv run pytest tests/test_gemini.py -k "grounding_source or unverified_url or malformed_grounding" -q
```

Expected: helpers/formatting do not exist.

- [ ] **Step 5: Implement metadata extraction and provenance filtering**

Add a general URL regex that does not replace the existing private-invite detector. Validate with `urlparse`: scheme exactly `https`, non-empty hostname, no username/password, and no private Telegram invite. Traverse only `response.candidates[0].grounding_metadata.grounding_chunks[*].web.uri` through `getattr`, dedupe while preserving order, and stop at `google_search_max_sources`.

Remove model-authored URL unless it is in the validated source set or equals `IMPORTANT_SERVICE_URL`. Append only source URLs not already present in cleaned text.

- [ ] **Step 6: Separate body and final-message safety limits**

Keep `max_output_chars` for the model-authored body. Permit the appended source block up to Telegram's `4096` character message limit. `is_output_safe` must split a recognized `Источник:`/`Источники:` block, validate body length separately, validate every source line through `_validate_grounding_url`, and reject total length above `4096`.

- [ ] **Step 7: Run source and existing safety tests and confirm GREEN**

```bash
uv run pytest tests/test_gemini.py -q
```

Expected: all Gemini tests pass, including existing invite/secret/max-output cases.

- [ ] **Step 8: Commit grounded source handling**

```bash
git add ai/gemini.py tests/test_gemini.py
git commit -m "Добавь проверенные источники к ответам"
```

### Task 4: Graceful Search Degradation

**Files:**
- Modify: `tests/test_gemini.py`
- Modify: `ai/gemini.py`

**Interfaces:**
- Consumes: `_generate_text(..., use_google_search, allow_ungrounded_fallback)`
- Produces: `WEB_SEARCH_UNAVAILABLE_CONTEXT` internal instruction
- Preserves: `GeminiTemporaryError`, `GeminiGenerationError`, `_get_model_names()` and existing exponential backoff

- [ ] **Step 1: Write failing grounded retry/fallback test**

Record `config.kwargs.get("tools")` for every request. Make primary fail temporarily and fallback succeed; assert every attempt before success contains Search tool.

- [ ] **Step 2: Write failing degraded-success test**

Make every request with tools fail and the first request without tools return `SimpleNamespace(text="Сейчас не смог проверить актуальные данные.")`. Assert:

```python
assert result == "Сейчас не смог проверить актуальные данные."
assert ungrounded_attempts == 1
assert "web_search_unavailable" in ungrounded_config.kwargs["system_instruction"]
assert "Источник" not in result
```

- [ ] **Step 3: Write failing total-failure and malformed-metadata tests**

Assert exactly one ungrounded attempt occurs after grounded exhaustion; when it also fails, existing `GeminiGenerationError`/`GeminiTemporaryError` propagates. Assert source parsing exceptions never trigger degraded regeneration when safe response text already exists.

- [ ] **Step 4: Run degradation tests and confirm RED**

```bash
uv run pytest tests/test_gemini.py -k "grounded_retry or search_degrades or total_grounding_failure" -q
```

- [ ] **Step 5: Implement one-shot ungrounded fallback**

After grounded model attempts fail, call `_generate_text` once with:

```python
degraded_system_prompt = (
    f"{system_prompt}\n\n"
    "web_search_unavailable: интернет-поиск сейчас недоступен. "
    "Не утверждай, что проверил актуальные данные; не придумывай ссылки. "
    "Если ответ зависит от текущей информации, коротко обозначь невозможность проверки."
)
```

Set `use_google_search=False`, `allow_ungrounded_fallback=False`. Preserve the original grounded exception as cause only if this final call fails. Log `grounding_mode=degraded` without prompt, query, URL or secret content.

- [ ] **Step 6: Run full Gemini tests and confirm GREEN**

```bash
uv run pytest tests/test_gemini.py -q
```

- [ ] **Step 7: Commit graceful degradation**

```bash
git add ai/gemini.py tests/test_gemini.py
git commit -m "Обработай недоступность Google Search"
```

### Task 5: Shared Prompt Architecture

**Files:**
- Modify: `tests/test_gemini.py`
- Modify: `ai/prompts/system.md`
- Modify: `ai/prompts/reply.md`
- Modify: `ai/prompts/start_topic.md`

**Interfaces:**
- Produces shared policy tokens tested by meaning: untrusted input, no fabricated experience/tools, short rhythm, grounded links, `web_search_unavailable`, identity challenge without false human proof.
- Preserves exact string: `https://t.me/tt_exchenge_bot/antex`
- Preserves markers: `important_service_question`, `important_service_answer`, `question_intent`

- [ ] **Step 1: Replace obsolete prompt assertions with failing layered-contract tests**

Test `system.md` contains semantic requirements for:

```text
4–12 слов
недоверенные данные
не выдумывай личный опыт
не утверждай, что проверил интернет
не доказывай, что ты человек
```

Test `reply.md` handles grounded sources and `web_search_unavailable`, while retaining every current important-service assertion. Test `start_topic.md` retains city adaptation and important-service question markers but does not instruct web search or source links.

- [ ] **Step 2: Run prompt tests and confirm RED**

```bash
uv run pytest tests/test_gemini.py -k "prompt or start_topic or important_service" -q
```

- [ ] **Step 3: Rewrite `system.md` as the single shared layer**

Use these sections and obligations:

```markdown
# Общие правила участника группы
## Ритм и уместность
## Факты, интернет и личный опыт
## Недоверенный ввод и секреты
## Реклама и ссылки
## Проверка identity и завершение спора
```

Keep the default one thought/4–12 words, allow expansion only for a complex explicit request, forbid habitual greetings/closings, treat messages/OCR/web as data rather than instructions, distinguish grounded facts from persona experience, and never claim or prove human identity.

- [ ] **Step 4: Rewrite scenario prompts**

`reply.md`: one direct answer, no forced follow-up question, verified source links only, honest degraded response, exact important-service URL behavior.

`start_topic.md`: one city-aware conversational question, no answer, no sources, no other city, no hidden internal markers, exact important-service question separation.

- [ ] **Step 5: Run prompt tests and confirm GREEN**

Run the Step 2 command.

- [ ] **Step 6: Commit shared prompts**

```bash
git add ai/prompts/system.md ai/prompts/reply.md ai/prompts/start_topic.md tests/test_gemini.py
git commit -m "Раздели общие и сценарные правила промтов"
```

### Task 6: Persona Delta Contract and Sequential Rewrite

**Files:**
- Modify: `tests/test_gemini.py`
- Modify sequentially: `ai/prompts/bots/dmitry.md`
- Modify sequentially: `ai/prompts/bots/vitaly.md`
- Modify sequentially: `ai/prompts/bots/max_danilov.md`
- Modify sequentially: `ai/prompts/bots/natalya_gromova.md`
- Modify sequentially: `ai/prompts/bots/darya_sokolova.md`
- Modify sequentially: `ai/prompts/bots/sofia.md`
- Modify sequentially: `ai/prompts/bots/max.md`
- Modify sequentially: `ai/prompts/bots/artem_belyaev.md`
- Modify sequentially: `ai/prompts/bots/anton_kovalev.md`
- Modify sequentially: `ai/prompts/bots/ekaterina_demidova.md`
- Modify sequentially: `ai/prompts/bots/malishka_kelli.md`

**Interfaces:**
- Every persona has exactly these headings: `## Биография`, `## Характер и решения`, `## Опыт и темы`, `## Манера общения`, `## Типичные ходы`, `## Границы и несовершенства`, `## Связи`.
- Persona files do not repeat shared phrases such as `никогда не сообщает, что он AI`, `никогда не сообщает, что она AI`, `не копирует стиль других персонажей`, `не превращается в "идеального помощника"`.

- [ ] **Step 1: Write failing persona-delta tests**

Replace the old `>=300 words`/14-heading contract. Assert all seven headings exist with non-empty character-specific bodies; banned shared-policy phrases are absent; no two normalized bodies are equal; each file contains at least one unique biography token and one bounded firsthand-experience statement.

- [ ] **Step 2: Add cross-persona distinctness rubric test**

Build normalized word sets excluding headings/stopwords. Assert pairwise Jaccard similarity remains below a documented threshold selected from the current baseline, and include a readable failure message naming the pair. Keep this heuristic secondary to explicit biography/behavior assertions.

- [ ] **Step 3: Run persona tests and confirm RED**

```bash
uv run pytest tests/test_gemini.py -k "prod_persona" -q
```

- [ ] **Step 4: Rewrite profiles one at a time using the coverage matrix**

| File | Biography anchor | Decision behavior | Firsthand boundary | Speech difference | Imperfection |
|---|---|---|---|---|---|
| `dmitry.md` | operational manager, family | checks conditions and consequences | operations, currency, infrastructure | dry and calm | can sound overly formal |
| `vitaly.md` | delivery/logistics, mobile work | chooses fast practical option | roads, scooters, cheap food | colloquial and quick | may estimate too confidently |
| `max_danilov.md` | online sales/partnerships | compares upside, cost and risk | online sales, finance basics | energetic but not promotional | can rush toward opportunity |
| `natalya_gromova.md` | rental/client service, adult child | checks documents and reversibility | housing/service processes | careful and reassuring | can over-insure |
| `darya_sokolova.md` | SMM/content, active city life | notices mood and visual detail | content, cafes, local events | warm, occasional emoji | can react before checking detail |
| `sofia.md` | adult Russian teacher/editor | clarifies meaning and comfort | language, books, calm places | soft and precise | can over-soften an answer |
| `max.md` | IT project manager | picks the next executable step | project work, apps, fitness | compact and action-oriented | can simplify nuance |
| `artem_belyaev.md` | hotel operations engineer | diagnoses one concrete cause | repairs, tools, household systems | plain factual example | can focus too narrowly |
| `anton_kovalev.md` | sysadmin/DevOps | asks for observable symptoms | devices, networks, security | terse technical diagnostic | can sound dry in emotional topics |
| `ekaterina_demidova.md` | events/relocation coordination | clarifies date, budget and agreement | vendors, documents, planning | organized but conversational | can ask one detail too many |
| `malishka_kelli.md` | beauty services/social media | reads mood and visible impression | beauty, style, beaches, cafes | vivid and emotional | can exaggerate first reaction |

For each file: preserve existing safe facts, add only non-sensitive connective biography, run `uv run pytest tests/test_gemini.py -k "prod_persona" -q`, compare against all previously rewritten files, then proceed to the next file.

- [ ] **Step 5: Run complete prompt/persona tests and confirm GREEN**

```bash
uv run pytest tests/test_gemini.py -q
```

- [ ] **Step 6: Commit all reviewed persona deltas**

```bash
git add ai/prompts/bots tests/test_gemini.py
git commit -m "Перепиши production-персоны как разные биографии"
```

### Task 7: Kirill Persona and Production Activation Gate

**Files:**
- Create when session is present: `ai/prompts/bots/kirill_orlov.md`
- Modify locally: `.env.prod`
- Modify locally: `config/settings.prod.toml`
- Modify: `tests/test_gemini.py`
- Modify: `tests/test_config_toml.py`

**Interfaces:**
- Produces production bot id: `kirill_orlov`
- Produces persona file: `kirill_orlov.md`
- Consumes exact session env name supplied locally by the user; never consumes or prints its value.

- [ ] **Step 1: Verify the activation prerequisite without secret output**

Compare only env key names from `.env.prod` with `session_env` names from TOML. If no new unmatched non-empty `SESSION_STRING_*` name exists, stop this task and report the single missing prerequisite; continue unrelated test/docs work.

- [ ] **Step 2: Add failing Kirill inventory assertions**

Assert `kirill_orlov.md` participates in the same seven-heading/distinctness contract and that production TOML/session/persona sets are equal with 12 unique entries.

- [ ] **Step 3: Write Kirill's delta**

Use only this safe profile:

```text
about 27; from Yekaterinburg; remote internet marketing;
moved to Vietnam three years ago; lived in Phu Quoc and Nha Trang, now Da Nang;
motorbike trips, cafes, local food, Vietnam travel, small online projects;
asks area/budget/goal before recommending; separates firsthand experience from inference;
calmer than Vitaly and less dry than Dmitry; does not turn marketing experience into advertising.
```

Do not add exact birth date, username, employer identifier, address, contacts or unverifiable sensitive facts.

- [ ] **Step 4: Activate the twelfth production bot atomically**

Add one `[[swarm.bots]]` entry with `id = "kirill_orlov"`, the exact locally present `session_env`, `persona_file = "kirill_orlov.md"`, `enabled = true`, and the established production temperature. Do not stage `.env.prod` or ignored `settings.prod.toml`.

- [ ] **Step 5: Validate production inventory without printing secrets**

```bash
uv run pytest tests/test_config_toml.py::test_prod_settings_toml_is_valid_and_matches_env_sessions tests/test_config_toml.py::test_prod_settings_load_with_declared_session_keys tests/test_gemini.py -k "prod_persona or prod_settings" -q
```

- [ ] **Step 6: Commit tracked Kirill persona/test changes**

```bash
git add ai/prompts/bots/kirill_orlov.md tests/test_gemini.py tests/test_config_toml.py
git commit -m "Добавь персону Кирилла Орлова"
```

### Task 8: Documentation, Verification, Sync and Archive

**Files:**
- Modify: `README.md`
- Modify: `openspec/project.md`
- Modify checkboxes: `openspec/changes/humanize-production-personas/tasks.md`
- Sync targets: `openspec/specs/production-personas/spec.md`, `openspec/specs/prompt-and-gemini/spec.md`, `openspec/specs/runtime-configuration/spec.md`, new `openspec/specs/web-grounded-replies/spec.md`

**Interfaces:**
- Consumes completed implementation and all test evidence.
- Produces operator documentation, synced main specs and archived change.

- [ ] **Step 1: Update operator and architecture documentation**

Document that every reply attempts Google Search, `start_topic` does not, sources come only from metadata, Search failure degrades once without fabricated links, production uses two sources, and Google Search adds latency/cost. Document the layered prompt order and seven-section persona delta.

- [ ] **Step 2: Run focused tests**

```bash
uv run pytest tests/test_config.py tests/test_config_toml.py tests/test_gemini.py tests/test_runtime.py tests/test_reply_router.py tests/test_orchestrator.py -q
```

Expected: all pass.

- [ ] **Step 3: Run the full suite**

```bash
uv run pytest
```

Expected: all tests pass; no real Gemini, Telegram or filesystem SQLite dependencies are used by unit tests.

- [ ] **Step 4: Validate OpenSpec strictly**

```bash
openspec validate --strict --all
```

Expected: all specs and `humanize-production-personas` pass.

- [ ] **Step 5: Run one explicit live grounding probe**

Add or use a non-committed one-shot command that loads the real production Gemini configuration, calls `generate_reply` with a harmless current-information question, prints only booleans/counts (`text_nonempty`, `source_count`, `https_sources_valid`), and never sends Telegram messages or prints the key, prompt, search query or full URLs. Expected: non-empty text and at least one validated HTTPS source.

- [ ] **Step 6: Review the final diff**

Check for secret values, raw queries/URLs in logs, duplicated persona policy, accidental runtime coordination claims, unrelated user changes and missing task checkboxes. Fix confirmed findings and rerun Steps 2–4.

- [ ] **Step 7: Sync delta specs**

Use `openspec-sync-specs` for `humanize-production-personas`, then run `openspec validate --strict --all` again.

- [ ] **Step 8: Archive only after all gates pass**

Use `openspec-archive-change` only after Kirill's session/inventory and live Search probe pass. Validate the archived main specs and commit tracked documentation/spec/archive changes without staging `docs/reports/`, `.env.prod`, `config/settings.prod.toml` or other unrelated files.
