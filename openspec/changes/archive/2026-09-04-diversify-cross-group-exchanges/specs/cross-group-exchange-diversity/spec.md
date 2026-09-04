## ADDED Requirements

### Requirement: Shared persisted diversity summary
The system SHALL build a separate cross-group scheduling summary over exchanges with `last_activity_at >= now - 24 hours`, using the caller-provided UTC time. The summary SHALL contain scheduling metadata only, identify groups by real chat id with group id as legacy fallback, and exclude records without either group identity. It SHALL count planned roles as reservations, started initiators as published and pending responders as reserved, and terminal roles only when their message ids confirm publication. Local history and published-only cooldown SHALL retain their group scope.

#### Scenario: Pending plan affects another group
- **WHEN** group G1 has a recent planned A/B exchange and G2 plans its exchange before G1 sends anything
- **THEN** G2 sees the reserved pair, participants, topic and service scenario in the shared summary
- **AND** G1's unsent roles are not treated as published participants in local cooldown

#### Scenario: Unpublished skipped exchange releases reservations
- **WHEN** an exchange is skipped before either role publishes
- **THEN** it contributes no participant, pair or topic reservation to subsequent decisions

#### Scenario: One-turn completion counts only published initiator
- **WHEN** a completed exchange contains only an initiator message id
- **THEN** its unsent responder and full pair do not count as published participation

#### Scenario: Old activity expires
- **WHEN** an exchange's last activity is strictly earlier than the supplied UTC time minus 24 hours
- **THEN** it does not influence the shared diversity score

### Requirement: Ranked random participant selection
The system SHALL choose distinct available participants by minimizing, in order: unordered-pair uses/reservations in other groups; the relaxation of the existing local cooldown prefix needed to admit both participants; their summed other-group participation; their summed all-group participation; and their summed all-group participation in the proposed roles. It SHALL choose randomly among equal scores. Both regular and important-service selection SHALL use this policy without making unavailable accounts eligible.

#### Scenario: Four bots across two fresh groups
- **WHEN** two fresh groups plan against the same four available bots and the second group sees the first group's plan
- **THEN** the second group selects the two remaining bots

#### Scenario: Fourteen bots across three fresh groups
- **WHEN** three fresh groups plan against the same fourteen available bots
- **THEN** their initial plans contain six distinct participants

#### Scenario: Reversing roles is still the same pair
- **WHEN** A/B was used in another group and an unused unordered pair is available
- **THEN** neither A/B nor B/A is selected

#### Scenario: Cross-group pair conflict overrides local cooldown
- **WHEN** the strict local candidate pool would repeat a pair from another group but relaxing the cooldown admits an unused pair
- **THEN** the system selects an unused pair with the smallest necessary cooldown relaxation

#### Scenario: Less-used participants win an otherwise equal comparison
- **WHEN** eligible pairs tie on pair conflicts, cooldown and other-group usage but differ in all-group participation
- **THEN** a pair with the lowest summed all-group participation is selected

#### Scenario: Many groups with small roster
- **WHEN** five fresh groups plan against four available bots
- **THEN** plans use distinct unordered pairs while alternatives remain, with participant reuse allowed
- **AND** no plan requires more bots than are actually available

#### Scenario: Only two bots remain
- **WHEN** only A and B are available and their pair has already been used in another group
- **THEN** an A/B exchange remains possible and the system logs the relaxed diversity preference without message content or secrets

### Requirement: Coordinated planning and participant replacement
The system SHALL serialize the shared-summary read, existing-window check, selection and persisted plan creation across orchestrators in one runtime. It SHALL release coordination before Telegram/LLM calls and waits. Restart SHALL preserve existing planned choices. Necessary replacement of an unsent participant SHALL use the same ranking with the counterpart fixed and the current exchange excluded from its own summary.

#### Scenario: Concurrent planning observes previous reservation
- **WHEN** two orchestrators plan concurrently using the same runtime store
- **THEN** one committed plan is visible before the other chooses its participants

#### Scenario: Restart resumes choices
- **WHEN** orchestrators are recreated after plans were saved
- **THEN** those plans retain their participants, topic and due time and influence other groups' new decisions

#### Scenario: Failed persistence leaves no reservation
- **WHEN** plan creation fails before commit
- **THEN** a later attempt is not influenced by an in-memory reservation from the failed attempt

#### Scenario: Participant replacement respects diversity
- **WHEN** a persisted unsent participant becomes unavailable
- **THEN** replacement ranking considers other groups with the counterpart fixed, does not choose the failed account, and does not resend an already published turn

### Requirement: Cross-group ordinary topic preference
The system SHALL rank ordinary topics by their number of recent other-group uses/reservations within the existing local fresh-topic pool, or the full pool if no locally fresh topic exists, choosing randomly among equal minima. It SHALL preserve the existing selector fallback when no topic list is available.

#### Scenario: Another fresh topic exists
- **WHEN** locally fresh topics X and Y exist and another group has recently reserved X but not Y
- **THEN** the system selects Y

#### Scenario: All topics used elsewhere
- **WHEN** every eligible topic has recent other-group use
- **THEN** the system chooses a least-used eligible topic and continues scheduling
