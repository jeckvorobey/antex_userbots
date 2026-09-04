## ADDED Requirements

### Requirement: Every generated reply uses Google Search grounding
The system SHALL enable the Google Search tool for every `generate_reply` call when production grounding is enabled.

#### Scenario: Addressed reply uses search
- **WHEN** an addressed human reply is generated with grounding enabled
- **THEN** the Gemini request includes `GoogleSearch` in `GenerateContentConfig.tools`

#### Scenario: Scheduled responder uses search
- **WHEN** responder B generates the answer in a scheduled exchange with grounding enabled
- **THEN** the Gemini request includes the same Google Search tool

#### Scenario: Start topic does not search
- **WHEN** `start_topic` generates an initiator question
- **THEN** its Gemini request does not include Google Search tools

### Requirement: Published sources come from grounding metadata
The system SHALL publish only validated web sources returned by Gemini grounding metadata and the explicit allowlisted important-service URL.

#### Scenario: Grounded sources are appended
- **WHEN** a reply contains web grounding chunks with valid HTTPS URLs
- **THEN** the final Telegram text appends the configured number of unique sources in metadata order

#### Scenario: Source count is capped
- **WHEN** grounding metadata contains more sources than `google_search_max_sources`
- **THEN** only the first configured number of unique valid sources is appended

#### Scenario: Duplicate source is emitted once
- **WHEN** multiple grounding chunks contain the same normalized HTTPS URL
- **THEN** the final Telegram text contains that source once

#### Scenario: Unsafe source is ignored
- **WHEN** a grounding chunk contains a non-HTTPS URL, embedded credentials, a private Telegram invite, or a malformed URI
- **THEN** that source is not included in the Telegram text

#### Scenario: Missing metadata does not invent a source
- **WHEN** Gemini returns reply text without grounding metadata or valid web chunks
- **THEN** the reply contains no generated source URL and the absence is logged without message contents

### Requirement: Model-authored URLs require provenance
The system SHALL prevent an arbitrary URL written only in model response text from being presented as a grounded source.

#### Scenario: Ungrounded model URL is removed
- **WHEN** response text contains a URL that is absent from grounding metadata and is not allowlisted
- **THEN** the URL is removed before the response is returned to Telegram callers

#### Scenario: Grounded model URL is preserved
- **WHEN** response text contains a URL that matches a validated grounding source
- **THEN** the URL may remain and is not duplicated in the appended source block

#### Scenario: Important-service URL remains allowed
- **WHEN** an `important_service_answer` contains `https://t.me/tt_exchenge_bot/antex`
- **THEN** that exact URL remains permitted independently of Google Search grounding

### Requirement: Grounded generation preserves safety and resilience
The system SHALL apply existing input redaction, retry, model fallback, graceful Search degradation, and output safety behavior to grounded reply generation.

#### Scenario: Secrets are redacted before search
- **WHEN** history or user input contains a token-like value or private Telegram invite
- **THEN** Gemini and Google Search receive only the redacted prompt representation

#### Scenario: Retry retains grounding
- **WHEN** a grounded Gemini request fails temporarily and is retried
- **THEN** every retry uses Google Search grounding

#### Scenario: Fallback retains grounding
- **WHEN** generation switches from the primary to fallback model
- **THEN** the fallback request also uses Google Search grounding

#### Scenario: Search outage degrades to one ungrounded request
- **WHEN** grounded attempts on the primary and fallback models fail because Google Search is unavailable or unsupported
- **THEN** the client performs at most one generation request without tools and marks its prompt with `web_search_unavailable`

#### Scenario: Degraded reply is honest
- **WHEN** ungrounded fallback answers a request that depends on current web information
- **THEN** it states briefly that current information could not be verified and does not claim to have searched the internet

#### Scenario: Degraded reply has no sources
- **WHEN** ungrounded fallback succeeds
- **THEN** the returned Telegram text contains no fabricated source block or arbitrary model URL

#### Scenario: Invalid grounding metadata preserves safe text
- **WHEN** Gemini returns non-empty safe text but grounding metadata is missing, partial, or malformed
- **THEN** invalid sources are ignored and the safe text is returned without raising a metadata-processing error

#### Scenario: Total Gemini failure remains explicit
- **WHEN** grounded generation and the single ungrounded fallback generation both fail
- **THEN** the client raises the existing generation error for caller-level handling without terminating the swarm process

#### Scenario: Final output is safety checked
- **WHEN** grounded reply text and source links are assembled
- **THEN** the final message is checked for secret-like content, private invites, mention limits, and configured total size before publication

### Requirement: Grounding deployment is verified
The system SHALL provide a controlled verification path for the configured production Gemini credentials.

#### Scenario: Live grounding probe succeeds
- **WHEN** the operator runs the explicit live grounding verification with production configuration
- **THEN** exactly one non-Telegram Gemini request returns non-empty text and at least one valid HTTPS grounding source
