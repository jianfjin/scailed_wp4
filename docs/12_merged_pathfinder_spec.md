# Merged Pathfinder V1 Product Spec

Date: 2026-05-15

Status: Draft for Epidata/DataWego alignment

Primary sources:

- `docs/5PROPOSAL_101314097-SCAILED-EU4H-2026-SANTE-PJ-PART_B_Section_1.pdf`, pages 41-44
- `docs/01_epidata_role.md`
- `docs/04_datawego_deliverables.md`
- `docs/07_data_from_other_partner.md`
- `docs/09_sample_data_availability.md`
- `council_debate_20260513/en/00_council_resolution.md`
- `council_debate_20260513/en/09_expanded_analysis.md`

## Decision

Pathfinder V1 should use the council design as the delivery base and absorb the strongest product elements from `docs/`.

The `docs/` design is a strong long-term platform vision, but it is too broad for the D4.1 V1/demo subcontract scope. The council design is more deliverable because it narrows Pathfinder V1 to an auditable, deterministic EHDS readiness path planner with clear upstream data contracts and contract-risk controls.

## One-Line Product Definition

Pathfinder V1 is an auditable EHDS readiness path planner: stakeholders answer structured questions, see where they are on the roadmap, receive traceable next steps, and export evidence for review.

## Proposal Ground Truth

The proposal says WP4 must develop:

- self-evaluation tools
- operating principles and procedures
- navigation tools
- stakeholder-specific current-state and next-step guidance
- regulatory constraints reflected in Pathfinder recommendations
- V1/demo delivery under D4.1 by M20

It also says Pathfinder must be validated and iterated with WP5, WP6, and WP7 feedback, while receiving input from WP2, WP3, and WP8.

## Product Goals

1. Let each stakeholder locate their current position against the strategic roadmap.
2. Produce actionable next steps by stakeholder type.
3. Make every recommendation traceable to roadmap nodes and regulatory rules.
4. Support D4.1 demo and D4.2 stakeholder event feedback.
5. Work before complete consortium data exists by using realistic mock data and confidence markers.
6. Keep V1 small enough to deliver within the likely Epidata subcontract budget.

## Non-Goals for V1

- No production multi-tenant SaaS.
- No AI copilot or GraphRAG recommendation generation.
- No automated legal decision-making.
- No direct HDAB, SPE, AI Factory, or hospital system integration.
- No Kubernetes/Helm/Terraform production platform.
- No Neo4j dependency.
- No full user-management system with registration, password reset, or OAuth.
- No V2 guideline authoring for D4.4 unless separately contracted.

## Users

Primary V1 users:

- Epidata and Charite WP4 reviewers
- WP2 stakeholder forum participants
- WP3 roadmap contributors
- WP5 health data infrastructure partners
- WP6 use case teams
- WP7 AI Factory/SPE partners
- WP8 regulatory and ethics reviewers

Representative stakeholder types:

- biotech SME
- AI Factory operator
- Health Data Access Body
- health data infrastructure
- research infrastructure
- regulator or ethics reviewer
- clinical/research use case team

## V1 User Flow

1. User opens invited Pathfinder demo link.
2. User selects stakeholder type and target scenario.
3. User completes guided readiness questionnaire.
4. Pathfinder maps answers to a stakeholder profile and current roadmap position.
5. Pathfinder evaluates regulatory and operational constraints.
6. Pathfinder returns a ranked path of next steps.
7. User sees traceability: rule, source, roadmap node, confidence, and missing data markers.
8. User exports an assessment report for review or stakeholder-event discussion.

## Functional Requirements

### F1. Guided Assessment

Pathfinder must provide stakeholder-specific questionnaires with:

- dynamic sections
- single-choice and multi-choice questions
- numeric readiness levels
- conditional questions
- answer validation
- versioned questionnaire definitions

### F2. Stakeholder Profile Model

Pathfinder must convert answers into a structured stakeholder state containing:

- stakeholder type
- target use case
- relevant infrastructure context
- maturity dimensions
- known capabilities
- missing capabilities
- regulatory flags
- confidence score based on input completeness

### F3. Roadmap Positioning

Pathfinder must map a stakeholder state to one or more roadmap nodes using:

- WP3 roadmap graph
- maturity dimensions
- prerequisites
- stakeholder applicability rules
- fallback generic roadmap when WP3 data is incomplete

### F4. Path Planning

Pathfinder must generate feasible next-step paths from current state to target state.

Each path must include:

- ordered roadmap steps
- prerequisites
- blockers
- effort estimate
- regulatory constraints
- source references
- confidence markers

### F5. Rule Engine

Pathfinder must use deterministic rules for compliance and recommendation logic.

Rules must support:

- eligibility
- exclusion
- preference
- override
- parent-child rule trees
- priority
- effective dates
- source references
- static validation before load
- test cases per rule file

### F6. Traceability

Every recommendation must show:

- source questionnaire answers
- roadmap node IDs
- triggered rule IDs
- regulatory references
- upstream data snapshot version
- schema version
- confidence level

### F7. Reporting

Pathfinder must export a V1 assessment report containing:

- organization/session summary
- stakeholder type
- readiness snapshot
- recommended path
- blockers and gaps
- compliance traceability
- missing-data warnings
- demo/non-production disclaimer where applicable

### F8. Admin Data Loading

Pathfinder must allow controlled loading and validation of:

- WP2 stakeholder taxonomy
- WP3 roadmap data
- WP8 rule files
- mock demo data
- rule test files

### F9. Graceful Degradation

If upstream data is incomplete, Pathfinder must continue in a reduced mode rather than fail.

Examples:

- missing WP3 labels -> route still works, labels marked incomplete
- missing maturity values -> default level with warning
- missing WP8 rules -> compliance marked unverified
- all upstream missing -> demo mode with mock data banner

### F10. Audit Trail

Pathfinder must append audit events for:

- assessment session creation
- answer submission
- recommendation generation
- report export
- rule reload
- data import
- graceful degradation events

Audit records must be append-only and chained by previous-hash values.

## Data Requirements

### Required by M3 Baseline

From WP2:

- stakeholder taxonomy
- personas
- user journeys
- stakeholder feedback categories

From WP3:

- roadmap nodes
- roadmap edges/prerequisites
- maturity dimensions
- KPI definitions
- stakeholder applicability mapping

From WP8:

- regulatory constraint rules
- regulatory references
- conflict/priority guidance
- known-rule test cases

### Acceptable Formats

Preferred:

- JSON
- YAML
- CSV
- JSON Schema
- OpenAPI
- BPMN/Mermaid

Accepted with extraction effort:

- Markdown
- DOCX
- PDF
- PPTX

Unstructured-only delivery is a project risk and must trigger the extraction fallback plan.

## Acceptance Criteria

V1 is accepted when:

- supports at least 5 stakeholder types
- provides at least 1 complete questionnaire per stakeholder type
- generates at least 3 executable paths across demo stakeholder types
- each generated recommendation has rule and roadmap traceability
- known WP8 rules in the agreed test set match expected outcomes
- standard questionnaire submission returns in 3 seconds or less at p95 in demo scale
- report export works for completed assessments
- Docker Compose deployment can be started by technical reviewers using documentation
- audit log records answer, recommendation, import, reload, and export events
- mock-data mode is clearly labeled when real upstream data is missing

## Quality Requirements

- Core path planning and rule evaluation must be deterministic.
- Core engine tests should target near-complete branch coverage.
- API/frontend shell coverage can be lower but must cover critical flows.
- Rule files must have paired test cases.
- Data imports must validate schema before activation.
- Errors must be explicit and user-safe.
- V1 must avoid storing direct personal data where possible.

## Security and Privacy Requirements

V1 should use minimal invited access:

- bearer token or single-use demo access links
- no public self-registration
- no password-management system
- no patient data
- no direct production EHDS data
- hashed IP/user-agent fields in audit logs
- HTTPS in deployed demo mode
- admin endpoints protected and rate-limited

WP8, Epidata, and Charite remain responsible for formal GDPR/DPIA and legal interpretation.

## V1 Scope Boundaries

Included:

- Pathfinder V1 software
- deterministic rules and path planner
- questionnaire UI
- roadmap visualization at demo level
- report export
- mock-data package
- import/validation tooling
- Docker Compose deployment package
- technical documentation for D4.1

Excluded unless separately contracted:

- V2 product expansion
- production hosting/operations
- real HDAB/SPE/AI Factory integration development
- multilingual UX
- full authentication and account management
- legal report writing for D4.3/D4.4
- AI copilot, RAG, GraphRAG, or LLM-generated recommendations

## Key Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| WP3 delivers only PDF/PPT | Critical | Require structured format or funded extraction layer |
| WP8 rules not formalized | High | Support soft checks, rule priorities, and "unverified" markers |
| Scope expands to full SaaS | Critical | Keep V1 bounded to D4.1 demo |
| Graph computation too slow | High | Use PostgreSQL AGE as primary graph engine |
| Legal/IP boundary unclear | High | Maintain per-file IP boundary document |
| Schema not signed by M3 | High | Auto-extend to M5 or switch to mock-data baseline |
| Upstream changes after baseline | High | Use versioned schemas and change-control process |

## Product Positioning

Use externally:

"Pathfinder helps stakeholders understand where they are on the EHDS readiness roadmap and what practical next steps they can take. Each recommendation is traceable to structured roadmap and regulatory inputs."

Avoid externally:

- "AI copilot"
- "automated compliance decision"
- "black-box AI"
- "production EHDS integration"
- "full navigation system" without human decision caveat

