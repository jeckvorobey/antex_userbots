## Context

The project generates bot voice through base prompt files plus persona overlays. Existing persona profiles describe communication style in detail, but several `## Манера общения`, chat behavior, and habits sections present words like "кстати", "слушай", "слушайте", and "смотри" as frequent interjections, favorite turns of phrase, or message starts. Recent feedback says bots are recognizable because real participants usually start with "привет", "всем привет", "здравствуйте", or ask directly without a lead-in.

The change is persona content plus one shared start-topic opening rule. It must preserve the current swarm runtime, scheduler, database schema, configuration model, and service-link behavior.

## Goals / Non-Goals

**Goals:**

- Make generated openings less bot-like by editing production persona communication style and the shared start-topic prompt.
- Convert the feedback into testable EARS-style requirements:
- When a production persona describes communication style, it shall not present marker-openers as frequent interjections, favorite phrases, or habitual starts.
- When a production persona describes starts, it shall use natural human patterns such as direct answers, direct questions, immediate reactions, or simple greetings.
- When the shared start-topic prompt defines how to begin a question, it shall use ordinary-human variants: `привет`, `всем привет`, `здравствуйте`, or a question without an introductory word.
- Keep acceptable human starts broad: direct question/answer, no introductory word, or simple greeting when the context makes a greeting natural.
- Add file-level tests so future persona edits do not reintroduce marker-openers into `## Манера общения`.

**Non-Goals:**

- No post-generation text rewriting or runtime filtering in `ai/gemini.py`.
- No new banned-word enforcement against arbitrary user messages, history, or base prompt files.
- No changes to important-service link behavior, exchange cadence, routing, persistence, or TOML format.
- No attempt to force every message to start with a greeting.

## Decisions

1. Put the improvement in `ai/prompts/bots/*.md`, not in separate persona restrictions.

   Rationale: the issue came from bot personalities and their described speech habits. Editing `## Манера общения` changes the persona voice directly without adding an extra prohibition layer.

   Alternative considered: add a new line under `## Ограничения`. Rejected because it makes the prompt heavier and leaves the old communication style contradicting the restriction.

2. Keep the base prompt change narrow.

   Rationale: `reply.md` does not need a global opener rule for this request. `start_topic.md` is the shared place for scheduled questions, so it should carry the explicit allowed opening variants.

   Alternative considered: add global prompt-level bans. Rejected because the requested behavior is a positive style rule, not a new ban list.

3. Test prompt/persona files directly.

   Rationale: this is a content contract. Existing tests already validate prompt and persona inventory/content, so focused assertions in `tests/test_gemini.py` should cover persona communication style without external Gemini calls.

   Alternative considered: mock Gemini and assert generated text. Rejected because generation is nondeterministic and the project avoids tests coupled to external AI behavior.

## Risks / Trade-offs

- Over-editing could flatten character voice → Mitigation: edit only the wording that makes marker-openers habitual and keep each persona's rhythm, topics, and tone.
- Tests could become too broad → Mitigation: test the `## Манера общения` section and avoid requiring a separate restriction phrase.
