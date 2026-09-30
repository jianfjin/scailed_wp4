# Volume 05 — API & Data Specification

## 1. Contract principles

The API is versioned under `/v1`. JSON is the normative exchange format. Schemas are stored beside this volume and are the machine-readable contract. Every response that makes a recommendation carries version and trace fields where applicable.

## 2. Core entities

### Stakeholder profile

```json
{
  "stakeholder_type": "biotech-sme",
  "description": "Biotech SME",
  "capabilities": ["legal-basis", "data-catalog"],
  "pain_points": ["limited_regulatory_expertise"]
}
```

### Roadmap node

```json
{
  "node_id": "n0005",
  "label": "Establish governance framework v1",
  "dimension": "governance",
  "maturity_level": 1,
  "stakeholder_types": ["all"],
  "prerequisites": [],
  "source_wp": "WP3",
  "source_doc_ref": "roadmap-v1",
  "confidence": 0.99,
  "metadata": {"target_scenarios": ["secondary-use-readiness"]}
}
```

### Rule

Rules have an ID, type, priority, applicability, condition, action, regulatory references, source reference, version, effective dates, and optional parent. Generated or provisional rules must carry a warning and never be presented as an official legal conclusion.

### Recommendation trace

```json
{
  "answer_ids": ["governance_maturity", "data_maturity"],
  "roadmap_node_ids": ["n0005", "n0105"],
  "triggered_rule_ids": ["WP8-RULE-0001"],
  "regulatory_refs": ["GDPR-Art.5"],
  "upstream_snapshot_version": "wp3-2026-05-19",
  "schema_version": "1.0.0",
  "rule_version": "wp8-demo-1"
}
```

## 3. API surface

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Runtime mode, loaded snapshots, and import status. |
| GET | `/v1/questionnaires` | List selectable stakeholder types. |
| GET | `/v1/questionnaires/{stakeholder_type}` | Return a versioned questionnaire. |
| POST | `/v1/assessments` | Create an assessment session. |
| POST | `/v1/assessments/{id}/answers` | Submit answers and derive state. |
| POST | `/v1/assessments/{id}/recommendations` | Generate a path; optional backend selector. |
| GET | `/v1/assessments/{id}/report` | Return a traceable report. |
| GET | `/v1/assessments/{id}/report?format=html` | Return a browser/export representation. |
| POST | `/v1/admin/import` | Validate and stage an approved snapshot. |
| POST | `/v1/admin/reload` | Activate a validated snapshot. |

The normative OpenAPI document is [openapi/pathfinder-v1.yaml](openapi/pathfinder-v1.yaml). Deployments may expose a smaller subset for the demo, but the response semantics must remain compatible.

## 4. Versioning and compatibility

- URL version changes are reserved for breaking API changes.
- Schema versions change on field removal, semantic change, or incompatible type change.
- Additive optional fields are backward compatible.
- Snapshot versions are immutable identifiers, not dates alone.
- Reports preserve the versions used to generate them.
- A migration note is required for any change to rule condition semantics or roadmap identifiers.

## 5. Validation rules

- maturity values are integers from 1 to 5;
- IDs are non-empty stable strings;
- a target scenario must be supported by the selected questionnaire;
- rules must validate against the rule schema before activation;
- roadmap edges must reference existing nodes;
- a rule test must identify expected status/action;
- unknown regulatory references are allowed only with an `unverified` marker;
- direct patient identifiers are not accepted by the demo contract.

## 6. Error contract

Errors use a stable `detail` message and an HTTP status appropriate to the failure. Validation errors identify the field or contract path. Import errors include the snapshot that failed and do not activate partial data. Internal exception details are not returned to participants.
