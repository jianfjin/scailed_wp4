# Volume 02 — Software Requirements Specification

## 1. Product boundary

Pathfinder V1 is a web-accessible assessment service with a deterministic domain engine. The core flow is:

```text
stakeholder + scenario → questionnaire → stakeholder state → rules + roadmap graph → path result → report
```

The service may use an in-memory graph for demo/fallback operation and a PostgreSQL-backed persistence layer where configured. Upstream WP2, WP3, and WP8 data is imported through versioned contracts.

## 2. Actors

| Actor | Permissions / responsibility |
| --- | --- |
| Demo participant | Selects a profile, runs an assessment, and views a report. |
| Reviewer | Examines evidence, warnings, trace, and exported report. |
| Data administrator | Loads and validates approved snapshots and rule bundles. |
| WP contributor | Supplies or reviews structured source data. |
| System operator | Runs the service, monitors health, and preserves logs. |

## 3. Functional requirements

### FR-01 Guided assessment

The system shall expose stakeholder-specific questionnaires with version, title, target scenarios, question IDs, answer types, options, requiredness, and conditional visibility. The baseline question dimensions are governance, data, and compliance maturity; capabilities; missing capabilities; and regulatory flags.

### FR-02 State derivation

The system shall convert submitted answers and/or approved WP2/WP3 source records into a `StakeholderState` containing stakeholder type, target scenario, maturity scores, capabilities, missing capabilities, regulatory flags, confidence, warnings, schema version, and upstream snapshot references.

### FR-03 Roadmap positioning

The system shall locate a current node and target node using stakeholder applicability, maturity dimensions, scenario metadata, and prerequisites. If labels or values are missing, it shall preserve the path where possible and emit a missing-data warning.

### FR-04 Rule evaluation

The system shall evaluate validated deterministic rules with atomic conditions and recursive `and`, `or`, and `not` expressions. Supported operators include `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `contains`, and `exists`.

### FR-05 Path planning

The system shall return an ordered path with current node, target node, next steps, blockers, warnings, backend, confidence, and triggered rule IDs. Blocking rules shall remove or prevent an infeasible route; non-blocking rules shall remain visible as guidance.

### FR-06 Traceability

Every recommendation shall retain answer IDs, roadmap node IDs, rule IDs, regulatory references, snapshot version, schema version, and rule version. Trace fields shall be present even when the result is blocked or degraded.

### FR-07 Reporting

The system shall export a reviewer-oriented report with session summary, readiness snapshot, path, blockers, warnings, trace evidence, audit-chain status, and a non-production/demo disclaimer where applicable.

### FR-08 Import and activation

The system shall validate WP2 stakeholder data, WP3 roadmap data, WP8 rules, and rule tests before activation. Invalid snapshots shall not silently replace the active version.

### FR-09 Audit

The system shall append events for session creation, answer submission, recommendation generation, report export, import, reload, and degradation. Events shall include event type, timestamp, subject reference, payload summary, and previous/current hash values.

### FR-10 Degradation

The system shall distinguish `ok`, `blocked`, and `degraded` results and explain the reason. Demo mode shall be visibly labeled.

## 4. Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-01 | Deterministic rule and path evaluation for identical versioned inputs. |
| NFR-02 | p95 standard assessment response at or below three seconds at demo scale. |
| NFR-03 | Schema validation before data activation. |
| NFR-04 | No patient data in the supplied demo fixtures. |
| NFR-05 | User-facing errors shall be explicit and shall not expose secrets or stack traces. |
| NFR-06 | Audit records shall be append-only from the application perspective. |
| NFR-07 | Every result shall identify data, schema, and rule versions where available. |
| NFR-08 | The demo shall be startable from documented commands by a technical reviewer. |
| NFR-09 | The user interface shall make blocked, degraded, and ready states visually distinct. |

## 5. Security and privacy requirements

- Use invited demo access or a bearer token; no public account creation is required for V1.
- Do not accept patient records or direct identifiers in the demo API.
- Hash or minimize IP and user-agent values in audit records.
- Protect import and reload operations separately from participant operations.
- Use HTTPS for any hosted demo.
- Treat pseudonymous data as personal data until the re-identification key is genuinely out of scope.
- Keep regulatory and clinical interpretation under human review; Pathfinder is decision support.

## 6. Requirements traceability matrix

| Requirement group | Primary evidence |
| --- | --- |
| FR-01–FR-03 | Volume 05 schemas, Volume 06 fixtures, assessment tests |
| FR-04–FR-06 | Rule schema, roadmap schema, path result trace |
| FR-07 | OpenAPI report endpoint and exported demo report |
| FR-08–FR-10 | Import validation, health endpoint, audit tests |
| NFR-01–NFR-09 | Volume 07 verification plan and demo evidence |

## 7. Acceptance status vocabulary

`ok` means the path can be presented as actionable within the available evidence. `blocked` means a rule or missing prerequisite prevents a path. `degraded` means a path was generated with incomplete or lower-confidence inputs. None of these statuses constitutes a legal or clinical determination.
