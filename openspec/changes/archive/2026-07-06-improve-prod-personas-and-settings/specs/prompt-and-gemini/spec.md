## ADDED Requirements

### Requirement: Persona overlays provide distinctive human behavior guidance
The system SHALL use production persona overlays that describe each character as a distinct living chat participant rather than a short generic assistant-like template.

#### Scenario: Persona keeps base identity
- **WHEN** a production persona profile is expanded
- **THEN** it preserves the character name, base role as a living chat participant, and existing high-level instruction not to mention AI or bot identity

#### Scenario: Persona guides varied replies
- **WHEN** Gemini composes a reply or scheduled exchange with a production persona
- **THEN** the persona overlay includes guidance for variable message length, questions, humor, disagreement, silence, and non-deterministic behavior

#### Scenario: Persona avoids identical output patterns
- **WHEN** production persona guidance is used across multiple bots
- **THEN** it instructs each character not to copy other characters' style or reuse identical constructions
