# FHIR Implementation Design

Date: 2026-06-11

Status: Proposed

Branch: `docs/fhir-implementation-proposal`

## Summary

Pathfinder should implement FHIR as a phased interoperability layer. The current Pathfinder domain model, deterministic solver, audit chain, and PostgreSQL schema remain authoritative for the first implementation phase. FHIR is added first as an export facade that emits FHIR R4 JSON Bundles from completed Pathfinder assessments, with explicit R5 compatibility notes and a documented migration path toward a future FHIR-native architecture.

The eventual target is approach C: FHIR resources become first-class persisted records and the Pathfinder engine operates from FHIR resources or a derived execution view. That target is documented now, but not implemented until export and REST facade behavior have been validated with partner use cases.

## Context

Pathfinder is currently a FastAPI-based EHDS readiness path planner. Users select a stakeholder type and target scenario, answer a questionnaire, receive deterministic recommendations, and export an auditable report. The implementation already has useful boundaries for FHIR integration:

- `AssessmentService` owns the assessment lifecycle.
- `QuestionnaireEngine` converts answers into `StakeholderState`.
- `PathfinderSolver` produces deterministic recommendations.
- Reports contain readiness snapshots, recommendations, trace data, audit validity, and warnings.
- The API has stable `/v1` assessment and report endpoints.
- The import layer already handles versioned WP2/WP3/WP8 data normalization.

FHIR fits this model because Pathfinder already uses questionnaire definitions, questionnaire answers, derived observations, workflow recommendations, organization context, provenance, and audit events. FHIR should represent these outputs without forcing an immediate rewrite of the core engine.

## Standards Position

Pathfinder should support a dual-version strategy:

- Generate FHIR R4 JSON first because R4 has the strongest real-world compatibility.
- Track R5 compatibility in mapping documentation because R5 is the current published HL7 specification.
- Avoid claiming full FHIR server conformance until Phase 2 exposes `CapabilityStatement` and read/search behavior.

Relevant HL7 references:

- FHIR overview: https://hl7.org/fhir/
- RESTful API: https://hl7.org/fhir/http.html
- CapabilityStatement: https://hl7.org/fhir/capabilitystatement.html
- Questionnaire: https://hl7.org/fhir/questionnaire.html
- QuestionnaireResponse: https://hl7.org/fhir/questionnaireresponse.html

## Goals

1. Export completed Pathfinder assessments as FHIR R4 JSON Bundles.
2. Include organization context, questionnaire definition, answers, derived readiness observations, recommendations, provenance, and audit evidence.
3. Preserve the current Pathfinder domain model and acceptance behavior.
4. Make resource IDs and references stable enough to support future `/fhir` read/search endpoints.
5. Document approach C as the future FHIR-native target architecture.

## Non-Goals

- No immediate rewrite of `AssessmentService`, domain dataclasses, or persistence around FHIR.
- No full FHIR server in Phase 1.
- No patient-level clinical data model.
- No invented patient data; stakeholder context is represented as `Organization`.
- No production EHDS/HDAB integration.
- No full implementation guide authoring in Phase 1.

## Phased Architecture

### Phase 1: FHIR Export Facade

Add a `pathfinder/fhir/` package that maps existing Pathfinder reports into FHIR resources. The export layer reads current assessment state and emits a `Bundle`.

The canonical flow remains:

```text
Questionnaire -> Answers -> StakeholderState -> Recommendation -> Report -> FHIR Bundle
```

The FHIR export layer must not rerun recommendation logic, mutate answers, or bypass audit. Exporting a FHIR Bundle records a new audit event, `fhir_bundle_exported`.

Recommended endpoint:

```text
GET /v1/assessments/{assessment_id}/fhir
```

This is clearer than overloading `report?format=fhir`, while still keeping the FHIR export connected to the existing `/v1` assessment contract.

### Phase 2: Limited FHIR REST Facade

After export mapping is stable, add read-oriented FHIR endpoints under `/fhir`:

```text
GET /fhir/metadata
GET /fhir/Bundle/{id}
GET /fhir/Questionnaire/{id}
GET /fhir/QuestionnaireResponse/{id}
GET /fhir/AuditEvent?entity={assessment_id}
```

`/fhir/metadata` returns a `CapabilityStatement` describing the limited resources and interactions Pathfinder supports. The server should only advertise implemented resources and interactions.

Phase 2 remains projection-based: FHIR resources are generated from Pathfinder state or retrieved from stored exported Bundles. Write/update/delete interactions are out of scope.

### Phase 3: Future FHIR-Native Target, Approach C

Approach C is the strategic end state. In that architecture, FHIR resources become first-class persisted records:

- questionnaires stored as `Questionnaire`
- answers stored as `QuestionnaireResponse`
- readiness and maturity state stored as `Observation`
- recommendations stored as `GuidanceResponse` plus `CarePlan`
- stakeholder context stored as `Organization`
- traceability stored as `Provenance`
- audit evidence stored or mirrored as `AuditEvent`

The solver can either consume FHIR directly or continue to use internal execution objects derived from FHIR resources. Persistence may evolve toward a generic resource table such as:

```text
resource_type
logical_id
version_id
subject_ref
payload
created_at
updated_at
```

Phase 3 should not start until Phase 1 exports and Phase 2 REST reads have partner validation.

## Resource Mapping

| Pathfinder concept | FHIR resource | Notes |
|---|---|---|
| Questionnaire definition | `Questionnaire` | One resource per stakeholder questionnaire version. |
| Submitted answers | `QuestionnaireResponse` | References the `Questionnaire` and assessed `Organization`. |
| Stakeholder type/context | `Organization` | Pseudonymous demo-safe organization; no patient identity. |
| Maturity scores | `Observation` | One grouped observation or one observation per maturity dimension. |
| Capabilities and missing capabilities | `Observation` | Use coded values where stable codes exist; otherwise Pathfinder coding system URIs. |
| Regulatory flags | `Observation` | Preserve existing flag values and regulatory references. |
| Confidence score/warnings | `Observation` | Confidence score is numeric; warnings are notes/components. |
| Recommendation status | `GuidanceResponse` | Captures ready/blocked status and trace status. |
| Next-step path | `CarePlan` | Ordered activities reference roadmap node identifiers. |
| Trace versions and source refs | `Provenance` | Records schema version, rule version, upstream snapshot, answer IDs, node IDs, and rule IDs. |
| Audit lifecycle | `AuditEvent` | Mirrors assessment creation, answer submission, recommendation generation, report export, and FHIR export. |
| Complete export | `Bundle` | Assessment package with stable internal references. |

Phase 1 does not include roadmap/rule metadata as first-class FHIR artifacts. Those may later map to `PlanDefinition` and `ActivityDefinition`, but doing so now would overfit the internal rule/roadmap engine before the assessment package is validated.

## Component Design

Add:

- `pathfinder/fhir/resources.py`: helpers for FHIR IDs, references, coding systems, timestamps, and Bundle entries.
- `pathfinder/fhir/mappers.py`: pure mapping functions from Pathfinder dictionaries/dataclasses to FHIR JSON dictionaries.
- `pathfinder/fhir/export_service.py`: orchestration that builds a full assessment Bundle.
- `pathfinder/fhir/capability.py`: Phase 2 generator for `CapabilityStatement`.
- `tests/test_fhir_export.py`: mapper, Bundle, and API coverage.

The mapper functions should stay mostly pure and deterministic. They should accept already-computed Pathfinder data and return JSON-serializable dictionaries.

## API Behavior

`GET /v1/assessments/{assessment_id}/fhir`:

- Requires the same invited demo token as report export.
- Returns `application/fhir+json` if practical, otherwise JSON with a FHIR Bundle body.
- Accepts optional `fhir_version=R4`, defaulting to `R4`.
- Returns a complete Bundle only after answers and recommendation exist.
- Appends `fhir_bundle_exported` to the audit chain on success.
- Appends `fhir_export_failed` on mapping failure when an assessment exists.

Errors:

- Missing assessment: `404 NOT_FOUND`.
- Unsupported FHIR version: `400 VALIDATION_ERROR`.
- Assessment missing answers or recommendation: `400 VALIDATION_ERROR`.
- Internal mapping invariant failure: `500 SERVER_ERROR`.

## Data Safety

FHIR export must not imply patient-level clinical interoperability. Pathfinder assesses organizational EHDS readiness, not patient care. Phase 1 therefore uses `Organization` as the subject/context and avoids `Patient` unless a future partner use case explicitly requires patient-level workflow integration.

FHIR resources should use pseudonymous logical IDs derived from assessment/session IDs. Raw IP addresses, raw user agents, and private organization identifiers must not be exported.

## Testing Strategy

1. Unit-test each mapper.
2. Add a golden Bundle test for one complete assessment.
3. Add API tests for auth, status codes, content type, and Bundle shape.
4. Add a regression test proving FHIR export does not change recommendation output.
5. Add an audit test proving successful export appends `fhir_bundle_exported`.
6. Add a failure-path test for unsupported FHIR versions.
7. Add an acceptance test requiring stable intra-Bundle references among `Questionnaire`, `QuestionnaireResponse`, `Organization`, `Observation`, `GuidanceResponse`, `CarePlan`, `Provenance`, and `AuditEvent`.

## Open Decisions Deferred to Implementation Plan

- Whether maturity scores are represented as one multi-component `Observation` or separate observations per dimension.
- Whether the recommendation uses only `GuidanceResponse`, only `CarePlan`, or both.
- Whether exported Bundles are persisted immediately or generated on demand in Phase 1.
- Exact Pathfinder coding-system URIs for stakeholder types, maturity dimensions, capabilities, flags, and roadmap nodes.

The implementation plan should choose conservative defaults and keep the mapper API narrow enough to revise after first validation.
