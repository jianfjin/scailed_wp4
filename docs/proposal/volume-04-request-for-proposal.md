# Volume 04 — Request for Proposal

## 1. RFP purpose

This RFP seeks delivery support for the SCAILED WP4 / EPIDATA Pathfinder V1 demonstrator. The supplier shall deliver a reviewable, deterministic EHDS readiness path planner and the documentation, data contracts, and evidence needed for D4.1 acceptance.

## 2. Expected supplier outcome

The supplier will provide a working demonstrator in a repository-managed doc-as-code and software workflow. A technical reviewer must be able to load approved fixtures, run an assessment for multiple stakeholder profiles, inspect traceability, and export a report.

## 3. Scope of services

### WP4-RFP-1 Product and UX

- confirm the guided assessment flow;
- implement stakeholder and scenario selection;
- display readiness, path, blockers, warnings, and evidence;
- provide a clear demo/non-production disclaimer.

### WP4-RFP-2 Deterministic assessment engine

- implement questionnaire and state derivation;
- implement roadmap positioning and path search;
- implement rule evaluation and priority handling;
- expose confidence and degraded states.

### WP4-RFP-3 Data contracts and imports

- validate WP2, WP3, and WP8 payloads;
- preserve snapshot and schema versions;
- reject invalid activation without destroying the current active version;
- include sample fixtures and paired rule tests.

### WP4-RFP-4 Traceability, audit, and reports

- record required events in an append-only audit chain;
- expose input, rule, roadmap, and regulatory references;
- export a reviewer report in HTML and/or PDF-ready form.

### WP4-RFP-5 Deployment and handover

- document local/demo deployment;
- provide Compose or equivalent reproducible packaging;
- provide test, smoke, and acceptance instructions;
- conduct a handover session for EPIDATA/Charité reviewers.

## 4. Mandatory deliverables

| ID | Deliverable | Acceptance evidence |
| --- | --- | --- |
| D-RFP-01 | Source repository and setup documentation | Fresh technical reviewer starts the demo. |
| D-RFP-02 | Guided assessment UI/API | At least five stakeholder types can be selected and assessed. |
| D-RFP-03 | Deterministic rules and path planner | Three executable paths plus blocked/degraded examples. |
| D-RFP-04 | Data schemas and import validation | Invalid fixture is rejected; valid snapshot is versioned. |
| D-RFP-05 | Traceable report export | Report contains path, blockers, trace, versions, and disclaimer. |
| D-RFP-06 | Audit trail | Session, answer, recommendation, import/reload, and export events present. |
| D-RFP-07 | Test and evidence pack | Automated checks, smoke run, and acceptance matrix. |
| D-RFP-08 | Handover and limitations register | Known gaps, assumptions, and future work recorded. |

## 5. Supplier response

The response should include:

- understanding of the V1 scope and non-goals;
- proposed architecture and technology choices;
- delivery plan mapped to the milestones in Volume 07;
- staffing and relevant experience in health data, interoperability, rules, or decision-support systems;
- quality, security, privacy, and testing approach;
- assumptions and dependencies on WP2/WP3/WP5/WP6/WP7/WP8;
- price by deliverable and any options;
- support and warranty period;
- examples of prior work and references.

## 6. Constraints

The supplier shall not introduce patient data into the demo; represent generated or unverified regulatory rules as authoritative; or expand V1 into production identity, direct infrastructure integration, AI copilot, or full cloud operations without an approved change request.

## 7. Evaluation criteria

| Criterion | Weight |
| --- | ---: |
| Understanding of scope and fit to D4.1 | 20% |
| Technical quality and determinism | 20% |
| Data contracts, traceability, and auditability | 15% |
| Demonstration and usability | 15% |
| Delivery plan and risk management | 15% |
| Team capability and relevant references | 10% |
| Cost and commercial clarity | 5% |

Minimum technical threshold: the response must explain how it will produce reproducible recommendations, validate partner data, and expose uncertainty.

## 8. Commercial and intellectual-property assumptions

The parties shall agree ownership, licensing, reuse rights, open-source obligations, dependency licenses, and treatment of partner-provided data before implementation. The supplier shall maintain a bill of materials and document any third-party service required for the demo.

## 9. RFP response checklist

- [ ] Scope and exclusions acknowledged.
- [ ] Deliverables mapped to acceptance evidence.
- [ ] Dependencies and assumptions listed.
- [ ] Security/privacy approach supplied.
- [ ] Test and handover plan supplied.
- [ ] Price and schedule supplied.
- [ ] IP and licensing position supplied.
