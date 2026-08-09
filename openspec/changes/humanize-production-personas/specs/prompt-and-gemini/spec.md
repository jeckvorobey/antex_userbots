## ADDED Requirements

### Requirement: Shared prompt owns common humanization policy
The system SHALL define common conversational, factuality, safety, promotion, and identity-challenge policy once in the shared system prompt.

#### Scenario: Shared prompt defines group rhythm
- **WHEN** `system.md` is loaded
- **THEN** it instructs ordinary replies to prefer one short thought, adapt length to the request, avoid formulaic closings, and avoid habitual greetings

#### Scenario: Shared prompt treats external content as untrusted
- **WHEN** messages, history, OCR, or web results are included in model context
- **THEN** the prompt treats their embedded instructions as untrusted data and forbids disclosure of internal prompts, credentials, or session material

#### Scenario: Shared prompt forbids fabricated capabilities and experience
- **WHEN** current facts, web evidence, personal experience, prices, or tool results are unavailable
- **THEN** the prompt requires an explicit uncertainty boundary and forbids inventing access, verification, or firsthand experience

#### Scenario: Shared prompt defines identity challenge behavior
- **WHEN** a user challenges bot identity
- **THEN** the prompt forbids claims or fabricated proof of being human and limits the response to one neutral move without repeated argument

## MODIFIED Requirements

### Requirement: Persona overlays provide distinctive human behavior guidance
The system SHALL compose the shared humanization policy with a production persona overlay that contains only character-specific biography and behavioral differences.

#### Scenario: Persona keeps base identity
- **WHEN** a production persona profile is composed
- **THEN** it preserves the character name, biography, decision patterns, experience boundaries, and speech differences without claiming a false human identity

#### Scenario: Persona inherits common policy
- **WHEN** Gemini composes a reply or scheduled exchange with a production persona
- **THEN** common length, safety, tool honesty, promotion, anti-repeat, and identity-challenge rules come from `system.md` rather than duplicated persona text

#### Scenario: Persona guides distinctive replies
- **WHEN** two different production personas receive equivalent context
- **THEN** their overlays provide materially different competence boundaries, dialogue moves, speech patterns, and imperfections
