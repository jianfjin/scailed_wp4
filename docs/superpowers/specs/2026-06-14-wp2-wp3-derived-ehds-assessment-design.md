# WP2/WP3-Derived EHDS Assessment Design

Date: 2026-06-14
Status: approved for implementation planning

## Goal

Pathfinder readiness assessment must be derived from project data, not client-entered readiness controls.

V1: Client selects stakeholder profile + scenario only.
V2: Backend derives readiness snapshot from WP2 stakeholder data + WP3 roadmap data.
V3: Solver keeps deterministic WP3 path + WP8 rule behavior.
V4: Report shows derived evidence + trace, not user-controlled sliders/checks.

## Problem

Current frontend renders editable `Governance readiness`, `Data readiness`, `Compliance readiness`, `Known capabilities`, `Missing capabilities`, and `Regulatory flags`.

Those values are submitted to `/answers/batch` and become `StakeholderState`. The graph uses maturity scores to locate current roadmap node. Compliance rules use capabilities, missing capabilities, and regulatory flags to trigger warnings/blockers.

This makes final assessment client-set. For WP4 Pathfinder, readiness should be assessment output from WP2/WP3/WP8 evidence.

## Architecture

Add server-side derivation layer:

```text
WP2 stakeholder record
  + WP3 roadmap graph
  + WP8 rule bundle
      -> DerivedReadinessService
      -> StakeholderState
      -> PathfinderSolver
      -> report + trace
```

Frontend:

```text
select stakeholder + scenario
  -> POST /v1/assessments
  -> POST /v1/assessments/{id}/recommendations
  -> GET /v1/assessments/{id}/report
```

No `/answers/batch` call from normal derived-assessment UI.

## Data Inputs

WP2 fixture records currently include:

- `stakeholder_type`
- `description`
- `capabilities`
- `pain_points`

WP3 roadmap nodes currently include:

- `node_id`
- `label`
- `dimension`
- `maturity_level`
- `stakeholder_types`
- `metadata.target_scenarios`
- `confidence`
- `source_doc_ref`

WP2 contract schema must be aligned with fixture shape by adding `capabilities` and `pain_points`.

## Derivation Policy

Initial capability-to-dimension map:

| Dimension | Capability Evidence |
| --- | --- |
| governance | `legal-basis`, `audit-log` |
| data | `data-catalog`, `data-quality-kpi`, `secure-processing`, `federated-analytics` |
| compliance | `legal-basis`, `secure-processing`, `audit-log` |

Maturity per dimension:

```text
coverage = present_dimension_capabilities / expected_dimension_capabilities
maturity = clamp(1, 5, round(1 + coverage * 4))
```

Required EHDS capability set:

```text
data-catalog
legal-basis
secure-processing
audit-log
data-quality-kpi
```

Derived missing capabilities:

```text
required EHDS capability set - WP2 capabilities
```

Pain point to regulatory flag map:

| WP2 pain point | Derived flag |
| --- | --- |
| `gdpr_ehds_alignment` | `gdpr-review-needed` |
| `ehds_interop_gap` | `ehds-rule-unverified` |
| `cross_border_data_governance` | `cross-border-use` |

Unmapped pain points remain trace evidence but do not create flags.

## API Behavior

`POST /v1/assessments` remains session creation.

`POST /v1/assessments/{id}/recommendations` must:

1. Resolve selected WP2 stakeholder record.
2. Derive `StakeholderState`.
3. Store derived readiness snapshot on session.
4. Run solver.
5. Store recommendation.

`POST /v1/assessments/{id}/answers/batch` remains available for compatibility/tests, but frontend must not call it in derived mode.

## Report Contract

Report `readiness_snapshot` must include:

- `derivation_mode: "wp2_wp3"`
- `stakeholder_type`
- `target_scenario`
- `maturity_scores`
- `capabilities`
- `missing_capabilities`
- `regulatory_flags`
- `pain_points`
- `confidence`
- `source_wp2_stakeholder_id`
- `source_wp2_snapshot_version`
- `source_wp3_snapshot_version`
- `confidence_warnings`

Recommendation trace must retain:

- answer ids, if legacy answers exist
- roadmap node ids
- triggered rule ids
- regulatory refs
- upstream snapshot version
- schema version
- rule version

Derived mode must expose evidence so reviewer can answer: which WP2 fields and WP3 nodes produced this recommendation?

## Frontend

Replace editable questionnaire controls with read-only derived evidence:

- selected stakeholder
- source WP2 capabilities
- source WP2 pain points
- derived maturity by dimension
- derived missing capabilities
- derived regulatory flags
- source snapshot/version

Primary action label becomes `Run derived assessment`.

No sliders/checklists for readiness in normal flow.

## Error Handling

If WP2 stakeholder record is missing:

- return validation error
- UI shows stakeholder data unavailable

If WP2 capabilities missing/empty:

- derive maturity `1` for all dimensions
- capabilities `[]`
- missing capabilities = full required set
- add confidence warning

If WP3 graph has no applicable path:

- keep existing solver blocker behavior
- report no feasible path with trace

If WP2 schema lacks `capabilities`/`pain_points`:

- import warning
- use empty lists
- lower confidence

## Testing

Backend tests:

- derived state uses WP2 capabilities.
- missing capabilities computed from required set.
- pain points map to regulatory flags.
- no submitted answers required for recommendation in derived mode.
- report contains derivation metadata.
- legacy `/answers/batch` flow still works.

Frontend tests:

- no readiness sliders/checklists rendered.
- run assessment does not call `/answers/batch`.
- report displays derived evidence.

Acceptance:

- changing client UI cannot alter readiness snapshot except by selecting another stakeholder/scenario.
- recommendation trace references WP2/WP3 evidence.

## Non-Goals

- No LLM-generated assessment.
- No free-form client overrides.
- No new database schema unless existing session storage cannot hold derived snapshot.
- No WP8 rule redesign.

