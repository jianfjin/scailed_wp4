## ADDED Requirements

### Requirement: Guided Stakeholder Assessment
Pathfinder V1 SHALL provide stakeholder-specific guided questionnaires that collect structured EHDS readiness inputs for invited demo users.

#### Scenario: Stakeholder starts assessment
- **GIVEN** an invited user has access to the Pathfinder demo
- **WHEN** the user selects a stakeholder type and target scenario
- **THEN** the system SHALL present the versioned questionnaire for that stakeholder type
- **AND** the questionnaire SHALL support dynamic sections, single-choice questions, multi-choice questions, numeric readiness levels, conditional questions, and answer validation

#### Scenario: Questionnaire version is preserved
- **WHEN** a user submits assessment answers
- **THEN** the system SHALL store the questionnaire version used for that submission

### Requirement: Stakeholder State Modeling
Pathfinder V1 SHALL convert questionnaire answers into a structured stakeholder state for planning and traceability.

#### Scenario: Answers become stakeholder state
- **WHEN** validated answers are submitted
- **THEN** the system SHALL produce a stakeholder state containing stakeholder type, target use case, infrastructure context, maturity dimensions, known capabilities, missing capabilities, regulatory flags, schema version, and confidence score

#### Scenario: Confidence reflects input completeness
- **WHEN** submitted answers omit optional or upstream-dependent data
- **THEN** the system SHALL lower the confidence score and identify the missing inputs that affected confidence

### Requirement: Roadmap Positioning
Pathfinder V1 SHALL map stakeholder state to roadmap positions using WP3 roadmap data and documented fallback behavior.

#### Scenario: Roadmap data is complete
- **GIVEN** WP3 roadmap nodes, edges, maturity dimensions, prerequisites, and stakeholder applicability mappings are loaded
- **WHEN** a stakeholder state is evaluated
- **THEN** the system SHALL map the stakeholder to one or more current roadmap nodes

#### Scenario: Roadmap data is incomplete
- **GIVEN** WP3 data is incomplete
- **WHEN** roadmap positioning runs
- **THEN** the system SHALL use a generic fallback roadmap where possible
- **AND** the result SHALL mark affected labels, maturity values, prerequisites, or applicability mappings as incomplete or provisional

### Requirement: Deterministic Path Planning
Pathfinder V1 SHALL generate feasible next-step paths from current stakeholder state to target state using deterministic logic.

#### Scenario: Feasible path exists
- **WHEN** a stakeholder has a current roadmap position and target state
- **THEN** the system SHALL return at least one ranked path with ordered roadmap steps, prerequisites, blockers, effort estimate, regulatory constraints, source references, and confidence markers

#### Scenario: No feasible path exists
- **WHEN** constraints or missing prerequisites prevent all paths
- **THEN** the system SHALL return an explicit blocker result rather than an empty or ambiguous recommendation

### Requirement: Deterministic Rule Engine
Pathfinder V1 SHALL use deterministic, versioned rules for compliance and recommendation logic.

#### Scenario: Rule bundle loads successfully
- **GIVEN** a rule bundle contains eligibility, exclusion, preference, or override rules
- **WHEN** an admin loads the rule bundle
- **THEN** the system SHALL parse it, validate it against the rule schema, compile it, scan conflicts, run paired rule tests, activate it only if validation passes, and record the active rule version or checksum

#### Scenario: Rule bundle fails validation
- **WHEN** a rule bundle fails schema validation, conflict checks, or paired rule tests
- **THEN** the system SHALL reject the new bundle
- **AND** the previous active rules SHALL remain active
- **AND** an audit event SHALL record the failed reload

### Requirement: Recommendation Traceability
Every Pathfinder V1 recommendation SHALL expose enough trace data for reviewer audit.

#### Scenario: Recommendation is generated
- **WHEN** the system returns a recommendation or path
- **THEN** the result SHALL show source questionnaire answers, roadmap node IDs, triggered rule IDs, regulatory references, upstream data snapshot version, schema version, rule version, and confidence level

#### Scenario: Upstream data changes later
- **WHEN** a recommendation is reviewed after upstream data has changed
- **THEN** the system SHALL retain the original schema, questionnaire, rule, and upstream snapshot versions that produced the recommendation

### Requirement: Assessment Report Export
Pathfinder V1 SHALL export a reviewer-facing assessment report for completed assessments.

#### Scenario: User exports report
- **GIVEN** an assessment has completed recommendation generation
- **WHEN** the user requests a report
- **THEN** the report SHALL include organization or session summary, stakeholder type, readiness snapshot, recommended path, blockers and gaps, compliance traceability, missing-data warnings, and demo or non-production disclaimers where applicable

### Requirement: Controlled Data Import
Pathfinder V1 SHALL provide controlled loading and validation of upstream and demo data.

#### Scenario: Admin imports structured data
- **WHEN** an admin imports WP2 stakeholder taxonomy, WP3 roadmap data, WP8 rule files, mock demo data, or rule test files in JSON, YAML, CSV, JSON Schema, OpenAPI, BPMN, or Mermaid-compatible structure
- **THEN** the system SHALL validate the input before activation, normalize IDs, calculate a checksum, store an upstream snapshot, and emit an import report

#### Scenario: Admin imports fallback document data
- **WHEN** upstream data arrives only as Markdown, DOCX, PDF, or PPTX
- **THEN** the system SHALL treat extraction as a fallback workstream
- **AND** extracted data SHALL be marked lower confidence until reviewed

### Requirement: Graceful Degradation
Pathfinder V1 SHALL continue in reduced mode when upstream data is incomplete and SHALL make that degradation explicit.

#### Scenario: Partial upstream data is missing
- **WHEN** WP2 taxonomy, WP3 labels, WP3 prerequisites, or WP8 rules are missing
- **THEN** the system SHALL continue where possible using generic questionnaires, node IDs, warnings, provisional prerequisites, or unverified compliance markers
- **AND** each degradation decision SHALL create an audit event

#### Scenario: All upstream data is missing
- **WHEN** no usable upstream inputs are available
- **THEN** the system SHALL run in mock-data demo mode
- **AND** the UI and exported report SHALL clearly label mock-data mode

### Requirement: Append-Only Audit Trail
Pathfinder V1 SHALL record append-only audit events for security, traceability, and reviewer evidence.

#### Scenario: Audited event occurs
- **WHEN** an assessment session is created, answers are submitted, recommendations are generated, a report is exported, rules are reloaded, data is imported, or graceful degradation occurs
- **THEN** the system SHALL append an audit record with a previous-hash value

#### Scenario: Audit record mutation is attempted
- **WHEN** any actor attempts to update or delete an audit record
- **THEN** the system SHALL reject the mutation and preserve the existing audit chain

### Requirement: V1 Access and Privacy Controls
Pathfinder V1 SHALL use controlled demo access and avoid direct personal or production EHDS data.

#### Scenario: Demo user accesses assessment flow
- **WHEN** a non-admin user accesses V1
- **THEN** the system SHALL require an invited bearer token or signed demo link
- **AND** the system SHALL NOT provide public self-registration, password reset, OAuth/OIDC login, or production account management

#### Scenario: Audit metadata is stored
- **WHEN** request metadata is included in audit logs
- **THEN** IP address and user-agent values SHALL be hashed rather than stored as direct identifiers

### Requirement: V1 Deployment Package
Pathfinder V1 SHALL provide a Docker Compose deployment package suitable for technical reviewers.

#### Scenario: Reviewer starts local deployment
- **WHEN** a technical reviewer follows the deployment documentation
- **THEN** Docker Compose SHALL start the frontend, backend, PostgreSQL with Apache AGE, reverse proxy, and supporting services without manual database edits

#### Scenario: Deployed demo mode is used
- **WHEN** Pathfinder V1 is deployed as a demo
- **THEN** HTTPS SHALL be provided through the configured reverse proxy in deployed demo mode
- **AND** PostgreSQL SHALL use a named volume outside the backend container

### Requirement: V1 Acceptance Baseline
Pathfinder V1 SHALL satisfy the D4.1 demo acceptance baseline before delivery.

#### Scenario: D4.1 acceptance is checked
- **WHEN** V1 is evaluated for D4.1 delivery
- **THEN** it SHALL support at least five stakeholder types
- **AND** it SHALL provide at least one complete questionnaire per stakeholder type
- **AND** it SHALL generate at least three executable paths across demo stakeholder types
- **AND** each recommendation SHALL have rule and roadmap traceability
- **AND** known WP8 rules in the agreed test set SHALL match expected outcomes
- **AND** standard questionnaire submission and recommendation generation SHALL return within three seconds at p95 demo scale
- **AND** report export SHALL work for completed assessments
- **AND** audit logs SHALL include answer, recommendation, import, reload, degradation, and export events
- **AND** mock-data mode SHALL be clearly labeled when real upstream data is missing
