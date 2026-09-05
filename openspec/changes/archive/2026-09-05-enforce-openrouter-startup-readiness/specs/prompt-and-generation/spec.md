## ADDED Requirements

### Requirement: Compatible provider routing
The system SHALL retain data_collection=deny and allow_fallbacks=true while omitting require_parameters=true for ordinary text generation and startup checks.

#### Scenario: Optional parameter support
- **WHEN** startup or a bot requests ordinary text generation
- **THEN** provider routing SHALL NOT exclude endpoints solely because they do not advertise support for every optional parameter
