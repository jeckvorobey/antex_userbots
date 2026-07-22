## ADDED Requirements

### Requirement: Production persona communication style starts naturally
The system SHALL describe production persona communication styles so bot messages can start like ordinary human chat messages instead of relying on recognizable repeated opener markers.

#### Scenario: Communication style avoids marker opener habits
- **WHEN** a production persona profile is read
- **THEN** its `## Манера общения` section does not list markers such as `кстати`, `слушай`, `слушайте`, or `смотри` as frequent interjections, favorite turns of phrase, or habitual message starts

#### Scenario: Communication style includes human starts
- **WHEN** a production persona profile describes communication style
- **THEN** it describes a natural start pattern such as a direct answer, a direct question, a simple greeting, or an immediate reaction that fits the character
