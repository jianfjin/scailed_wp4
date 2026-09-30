# Volume 07 — Project Plan & Deliverables

## 1. Delivery approach

Work proceeds through a doc-as-code and testable demonstrator workflow. Markdown, schemas, OpenAPI, diagrams, fixtures, and acceptance evidence live in version control. Partner inputs are versioned and changes are reviewed before activation.

## 2. Work breakdown

| Work package | Main outputs | Dependency |
| --- | --- | --- |
| WP4.1 Baseline | Scope, glossary, architecture, repository structure | Proposal approval |
| WP4.2 Requirements | SRS, use cases, acceptance matrix, traceability | WP4.1 |
| WP4.3 Data contracts | Schemas, import validation, fixture metadata | WP2/WP3/WP8 input shape |
| WP4.4 Engine | Questionnaire, state model, rule evaluator, path planner | WP4.2 + WP4.3 |
| WP4.5 Interface and reports | Guided UI/API, evidence view, export | WP4.4 |
| WP4.6 Integration and demo | Partner feedback, deployment, smoke run | WP4.4 + WP4.5 |
| WP4.7 Acceptance and handover | Evidence pack, limitations, handover | All prior work |

## 3. Milestones

| Milestone | Exit criteria |
| --- | --- |
| M1 Scope baseline | Volumes 01–03 reviewed; V1 non-goals agreed. |
| M2 Contract baseline | Schemas, OpenAPI, fixture metadata, and trace fields reviewed. |
| M3 Engine baseline | Assessment, deterministic rules, and path search pass unit tests. |
| M4 Demo baseline | Five stakeholder types, three paths, blocked/degraded cases, report export. |
| M5 Review baseline | WP2/WP3/WP5/WP6/WP7/WP8 feedback triaged and documented. |
| M6 D4.1 acceptance | Technical reviewer reproduces demo and evidence pack is complete. |

## 4. Acceptance test plan

| Test | Procedure | Pass condition |
| --- | --- | --- |
| AT-01 Startup | Start documented demo services. | Health endpoint reports mode and imports. |
| AT-02 Profile catalog | List questionnaires and inspect five profiles. | All profiles have usable questionnaire metadata. |
| AT-03 Assessment | Create session and submit valid answers. | State includes maturity, capabilities, confidence, and versions. |
| AT-04 Path | Generate recommendations for three cases. | Ordered steps and trace fields are returned. |
| AT-05 Block | Run a case with a blocking rule. | Status is `blocked` and reason is visible. |
| AT-06 Degrade | Remove or omit an upstream field. | Result is `degraded` or explicitly unverified, never silently complete. |
| AT-07 Report | Export a completed assessment. | Report contains summary, path, trace, warnings, disclaimer, and audit status. |
| AT-08 Import | Submit invalid and valid snapshots. | Invalid data is rejected; valid data activates only after validation. |
| AT-09 Audit | Inspect lifecycle events. | Create, answer, recommend, import/reload, and export events are linked. |
| AT-10 Performance | Run standard demo request repeatedly. | p95 response is at or below three seconds at demo scale. |

## 5. Governance and change control

The WP4 lead owns the product baseline. EPIDATA owns implementation coordination and technical evidence. Charité supports clinical/operational validation. WP2, WP3, WP5, WP6, WP7, and WP8 owners approve changes to their respective input contracts. A change that alters scope, legal interpretation, or an agreed acceptance criterion requires explicit review.

## 6. Risks and dependencies

- structured WP2/WP3/WP8 inputs are required for production-quality recommendations;
- WP8 must review rule semantics and regulatory references;
- WP3 must provide stable node IDs and prerequisites;
- WP5–WP7 feedback is needed to validate operational usefulness;
- scope growth toward SaaS, AI, or production integration must be treated as a separately approved change;
- demo data must remain synthetic and must not drift into patient data.

## 7. Handover package

The final handover contains the seven volumes, diagrams, schemas, OpenAPI, fixture inventory, setup instructions, test output, acceptance matrix, known limitations, dependency bill of materials, and a short live-demo script.

## 8. Definition of done

The project is complete when all mandatory deliverables are present, acceptance tests pass or have a documented approved exception, the demo is reproducible, every recommendation is traceable, limitations are explicit, and the responsible reviewers have signed off the V1 boundary.
