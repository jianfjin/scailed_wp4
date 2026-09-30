# Volume 01 — Executive & Business Requirements

**Programme:** SCAILED WP4 / EPIDATA Pathfinder
**Baseline:** Pathfinder V1 / D4.1 demo
**Status:** Proposal baseline
**Date:** 2026-09-30

## 1. Executive summary

Pathfinder is a practical navigation tool for the European Health Data Space (EHDS) ecosystem. It helps organizations understand their current readiness, identify gaps, and select credible next steps toward a target scenario such as secondary-use readiness.

The V1 product is intentionally narrow: it is a deterministic and auditable assessment-and-path-planning demonstrator. It uses structured WP2 stakeholder information, WP3 roadmap evidence, and WP8 regulatory rules. Every result carries source, version, confidence, and audit information so that a reviewer can understand how it was produced.

Pathfinder does not make legal decisions, replace a competent authority, or process patient data. It provides structured decision support for consortium review, stakeholder engagement, and D4.1 demonstration.

## 2. Business problem

Stakeholders approach EHDS secondary use from different starting points. Their capabilities, governance, infrastructure, and regulatory obligations vary, while roadmap and regulatory knowledge is distributed across work packages and documents. A static report cannot reliably answer:

- where a stakeholder currently sits;
- which prerequisites are missing;
- which next steps are feasible;
- why a recommendation was made; and
- which inputs still require expert confirmation.

The proposal addresses this fragmentation with one versioned, reviewable Pathfinder workflow.

## 3. Objectives and outcomes

| Objective | Observable outcome |
| --- | --- |
| Locate readiness | A stakeholder receives a structured readiness profile and roadmap position. |
| Recommend action | The system returns an ordered path, blockers, warnings, and prerequisites. |
| Preserve trust | Rules, roadmap nodes, answers, snapshots, and confidence are visible in the result. |
| Support collaboration | WP2, WP3, WP5, WP6, WP7, and WP8 contributors can review and refine inputs. |
| Demonstrate delivery | Reviewers can run the demo, load mock data, execute an assessment, and export a report. |

## 4. Stakeholders and value

| Stakeholder | Value from Pathfinder |
| --- | --- |
| WP4 reviewers | Repeatable evidence for D4.1 acceptance and stakeholder feedback. |
| WP2 stakeholder forum | A common language for profiles, capabilities, and pain points. |
| WP3 roadmap contributors | A machine-readable projection of milestones and prerequisites. |
| WP5 infrastructure partners | A way to express infrastructure readiness and integration gaps. |
| WP6 use-case teams | Scenario-specific preparation and next-step guidance. |
| WP7 AI Factory partners | Clearer prerequisites for secure processing and AI workflows. |
| WP8 legal/regulatory partners | A controlled place for rule bundles, references, and validation cases. |

## 5. V1 scope

Included:

- guided stakeholder assessment;
- maturity and capability profile;
- roadmap positioning and deterministic path planning;
- versioned rules and schema validation;
- traceability and append-only audit evidence;
- safe mock/demo data;
- HTML/report export and technical documentation;
- documented local or Compose-based demonstration.

Excluded from V1:

- patient or production EHDS data;
- public self-registration and full identity management;
- automated legal or clinical decisions;
- direct production integrations with HDABs, SPEs, hospitals, or AI Factories;
- LLM-generated recommendations, RAG, or GraphRAG;
- production Kubernetes, Terraform, or Helm operations;
- multilingual and full SaaS concerns.

## 6. Business requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| BR-01 | The solution shall support at least five representative stakeholder types. | Must |
| BR-02 | The solution shall provide one complete assessment flow per supported type. | Must |
| BR-03 | The solution shall produce at least three executable demo paths. | Must |
| BR-04 | Each recommendation shall expose roadmap and rule traceability. | Must |
| BR-05 | Incomplete upstream data shall result in explicit degraded-mode warnings, not silent failure. | Must |
| BR-06 | The demo shall avoid direct personal and patient data. | Must |
| BR-07 | The demonstration shall be reproducible by a technical reviewer using the documentation. | Must |
| BR-08 | The proposal shall preserve a clear path to future WP5/WP6/WP7 integration without making those integrations V1 dependencies. | Should |

## 7. Success measures

V1 is successful when the acceptance set in Volume 07 is evidenced: five or more stakeholder types, complete questionnaires, three executable paths, traceable recommendations, known rule tests, p95 response within three seconds at demo scale, report export, documented startup, and audit records for key events.

## 8. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| WP3 arrives only as PDF/PPT | Require structured roadmap exports or fund an explicit extraction step. |
| WP8 rules remain informal | Support an `unverified` state and require paired rule tests before activation. |
| V1 expands into a full platform | Keep the scope boundary and acceptance baseline in change control. |
| Stakeholder input changes after baseline | Version schemas, snapshots, rules, and questionnaires. |
| Regulatory interpretation is mistaken for legal advice | Show sources and warnings; require WP8 review and human decision ownership. |

## 9. Business acceptance statement

Pathfinder V1 is accepted as a demonstrator when a reviewer can follow a complete assessment from selected stakeholder profile through traceable recommendation and exported report, with all data versions, warnings, and audit events visible.
