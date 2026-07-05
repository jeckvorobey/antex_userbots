## ADDED Requirements

### Requirement: Topic key caching
The system SHALL cache normalized keys for loaded scheduled exchange topic intents.

#### Scenario: Topic selector caches normalized key
- **WHEN** `TopicSelector.load` reads a topic intent
- **THEN** `TopicSelector.topic_key(topic)` returns the normalized key without requiring callers to recompute it

#### Scenario: Orchestrator uses cached topic key when available
- **WHEN** scheduled topic anti-repeat evaluates topics from a `TopicSelector`
- **THEN** it uses the selector-provided topic key for recent-topic comparison

#### Scenario: Orchestrator preserves fallback for simple selectors
- **WHEN** scheduled topic anti-repeat receives a selector without `topic_key`
- **THEN** it falls back to normalizing the topic text directly
