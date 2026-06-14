# WP2/WP3-Derived EHDS Assessment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace client-entered readiness controls with server-derived EHDS readiness from WP2 stakeholder evidence and WP3 roadmap data.

**Architecture:** Add a focused derivation service that converts WP2 stakeholder records into `StakeholderState`, then feed the existing deterministic solver unchanged. Keep legacy `/answers/batch` available, but make normal recommendations derive state automatically when no submitted answers exist. Frontend selects stakeholder/scenario, runs recommendation, and renders read-only evidence from the report.

**Tech Stack:** Python dataclasses/FastAPI/Pydantic, pytest/TestClient, React/TypeScript/Vite, Node test runner.

---

## File Structure

- Create `pathfinder/services/derived_readiness.py`: pure derivation logic from WP2 record + target scenario to `StakeholderState`.
- Modify `pathfinder/services/assessment_service.py`: store WP2 records, use derivation for recommendation/report when no answers exist, add derivation metadata.
- Modify `pathfinder/api/schemas.py`: allow derived readiness fields in `readiness_snapshot`.
- Modify `docs/contracts/wp2_stakeholder_taxonomy.schema.json`: align contract with fixture fields `capabilities` and `pain_points`.
- Modify `frontend/src/main.tsx`: remove editable questionnaire from normal flow; call recommendation directly; render derived evidence.
- Add `tests/test_derived_readiness.py`: unit tests for derivation rules.
- Modify `tests/test_api.py`: API no longer requires `/answers/batch` for normal assessment.
- Modify `tests/test_d4_1_acceptance.py`: add derived-flow acceptance while preserving legacy tests.
- Add or extend frontend tests in `frontend/scripts/*.test.mjs` only if helpers are extracted; otherwise verify with `npm run build`.

---

### Task 1: Derived Readiness Unit

**Files:**
- Create: `pathfinder/services/derived_readiness.py`
- Test: `tests/test_derived_readiness.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_derived_readiness.py`:

```python
from pathfinder.services.derived_readiness import derive_readiness_state


def test_derive_readiness_uses_wp2_capabilities() -> None:
    state = derive_readiness_state(
        stakeholder={
            "stakeholder_type": "academic-spinout-001",
            "description": "Academic spinout",
            "capabilities": ["legal-basis", "secure-processing", "federated-analytics"],
            "pain_points": ["gdpr_ehds_alignment", "ehds_interop_gap"],
        },
        target_scenario="secondary-use-readiness",
        wp2_snapshot_version="wp2-test-v1",
        wp3_snapshot_version="wp3-test-v1",
    )

    assert state.stakeholder_type == "academic-spinout-001"
    assert state.target_scenario == "secondary-use-readiness"
    assert state.capabilities == ("federated-analytics", "legal-basis", "secure-processing")
    assert state.missing_capabilities == ("audit-log", "data-catalog", "data-quality-kpi")
    assert state.regulatory_flags == ("ehds-rule-unverified", "gdpr-review-needed")
    assert state.maturity_scores == {"governance": 3, "data": 3, "compliance": 4}
    assert state.answers["derivation_mode"] == "wp2_wp3"
    assert state.answers["source_wp2_stakeholder_id"] == "academic-spinout-001"
    assert state.answers["source_wp2_snapshot_version"] == "wp2-test-v1"
    assert state.answers["source_wp3_snapshot_version"] == "wp3-test-v1"
    assert state.confidence == 1.0


def test_derive_readiness_handles_missing_capabilities_with_warning() -> None:
    state = derive_readiness_state(
        stakeholder={
            "stakeholder_type": "empty-stakeholder",
            "description": "Empty stakeholder",
            "pain_points": ["cross_border_data_governance"],
        },
        target_scenario="secondary-use-readiness",
        wp2_snapshot_version="wp2-test-v1",
        wp3_snapshot_version="wp3-test-v1",
    )

    assert state.capabilities == ()
    assert state.maturity_scores == {"governance": 1, "data": 1, "compliance": 1}
    assert state.missing_capabilities == (
        "audit-log",
        "data-catalog",
        "data-quality-kpi",
        "legal-basis",
        "secure-processing",
    )
    assert state.regulatory_flags == ("cross-border-use",)
    assert state.confidence == 0.7
    assert "WP2 capabilities missing or empty" in state.confidence_warnings
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_derived_readiness.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pathfinder.services.derived_readiness'`.

- [ ] **Step 3: Implement derivation service**

Create `pathfinder/services/derived_readiness.py`:

```python
"""Derive Pathfinder readiness state from WP2/WP3 evidence."""

from __future__ import annotations

from typing import Any

from pathfinder.core.models import SCHEMA_VERSION, StakeholderState

REQUIRED_EHDS_CAPABILITIES = (
    "data-catalog",
    "legal-basis",
    "secure-processing",
    "audit-log",
    "data-quality-kpi",
)

CAPABILITIES_BY_DIMENSION = {
    "governance": ("legal-basis", "audit-log"),
    "data": ("data-catalog", "data-quality-kpi", "secure-processing", "federated-analytics"),
    "compliance": ("legal-basis", "secure-processing", "audit-log"),
}

PAIN_POINT_FLAGS = {
    "gdpr_ehds_alignment": "gdpr-review-needed",
    "ehds_interop_gap": "ehds-rule-unverified",
    "cross_border_data_governance": "cross-border-use",
}


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))


def _maturity_for(capabilities: set[str], expected: tuple[str, ...]) -> int:
    if not expected:
        return 1
    coverage = len(capabilities.intersection(expected)) / len(expected)
    return max(1, min(5, round(1 + coverage * 4)))


def derive_readiness_state(
    *,
    stakeholder: dict[str, Any],
    target_scenario: str,
    wp2_snapshot_version: str,
    wp3_snapshot_version: str,
) -> StakeholderState:
    stakeholder_type = str(stakeholder.get("stakeholder_type", "")).strip()
    capabilities = _string_list(stakeholder.get("capabilities"))
    pain_points = _string_list(stakeholder.get("pain_points"))
    capability_set = set(capabilities)

    maturity_scores = {
        dimension: _maturity_for(capability_set, expected)
        for dimension, expected in CAPABILITIES_BY_DIMENSION.items()
    }
    missing_capabilities = tuple(
        capability for capability in sorted(REQUIRED_EHDS_CAPABILITIES)
        if capability not in capability_set
    )
    regulatory_flags = tuple(
        sorted({PAIN_POINT_FLAGS[pain_point] for pain_point in pain_points if pain_point in PAIN_POINT_FLAGS})
    )

    warnings: list[str] = []
    confidence = 1.0
    if not capabilities:
        warnings.append("WP2 capabilities missing or empty")
        confidence = 0.7

    answers = {
        "derivation_mode": "wp2_wp3",
        "source_wp2_stakeholder_id": stakeholder_type,
        "source_wp2_snapshot_version": wp2_snapshot_version,
        "source_wp3_snapshot_version": wp3_snapshot_version,
        "pain_points": list(pain_points),
        "capabilities": list(capabilities),
        "missing_capabilities": list(missing_capabilities),
        "regulatory_flags": list(regulatory_flags),
        "maturity_scores": dict(maturity_scores),
    }

    return StakeholderState(
        stakeholder_type=stakeholder_type,
        target_scenario=target_scenario,
        answers=answers,
        maturity_scores=maturity_scores,
        capabilities=capabilities,
        missing_capabilities=missing_capabilities,
        regulatory_flags=regulatory_flags,
        confidence=confidence,
        confidence_warnings=tuple(warnings),
        questionnaire_version="derived-wp2-wp3-v1",
        schema_version=SCHEMA_VERSION,
        upstream_snapshot_version=wp3_snapshot_version or wp2_snapshot_version,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
pytest tests/test_derived_readiness.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add pathfinder/services/derived_readiness.py tests/test_derived_readiness.py
git commit -m "feat: derive readiness from WP2 evidence"
```

---

### Task 2: Backend Derived Recommendation Flow

**Files:**
- Modify: `pathfinder/services/assessment_service.py`
- Test: `tests/test_api.py`
- Test: `tests/test_d4_1_acceptance.py`

- [ ] **Step 1: Write failing API test**

In `tests/test_api.py`, add this method to `ApiTests`:

```python
    def test_assessment_flow_derives_readiness_without_answers_batch(self) -> None:
        api_main._service = None
        client = TestClient(app)
        headers = {"Authorization": "Bearer demo-token"}

        session = client.post(
            "/v1/assessments",
            headers=headers,
            json={
                "stakeholder_type": "academic-spinout-001",
                "target_scenario": "secondary-use-readiness",
            },
        )
        self.assertEqual(session.status_code, 200)
        assessment_id = session.json()["assessment_id"]

        recommendation = client.post(
            f"/v1/assessments/{assessment_id}/recommendations",
            headers=headers,
        )
        self.assertEqual(recommendation.status_code, 200)

        report = client.get(f"/v1/assessments/{assessment_id}/report", headers=headers)
        self.assertEqual(report.status_code, 200)
        snapshot = report.json()["readiness_snapshot"]

        self.assertEqual(snapshot["derivation_mode"], "wp2_wp3")
        self.assertEqual(snapshot["source_wp2_stakeholder_id"], "academic-spinout-001")
        self.assertIn("legal-basis", snapshot["capabilities"])
        self.assertIn("pain_points", snapshot)
        self.assertNotIn("answers_submitted", {
            event.event_type for event in api_main._get_service().audit_log.events()
        })
```

In `tests/test_d4_1_acceptance.py`, add:

```python
def test_d4_1_9_derived_assessment_uses_wp2_wp3_without_client_answers() -> None:
    api_main._service = AssessmentService()
    client = TestClient(app)
    headers = {"Authorization": "Bearer demo-token"}

    session = client.post(
        "/v1/assessments",
        headers=headers,
        json={
            "stakeholder_type": "academic-spinout-001",
            "target_scenario": "secondary-use-readiness",
        },
    )
    assert session.status_code == 200
    assessment_id = session.json()["assessment_id"]

    recommendation = client.post(
        f"/v1/assessments/{assessment_id}/recommendations",
        headers=headers,
    )
    assert recommendation.status_code == 200

    report_response = client.get(f"/v1/assessments/{assessment_id}/report", headers=headers)
    assert report_response.status_code == 200
    report = report_response.json()
    snapshot = report["readiness_snapshot"]

    assert snapshot["derivation_mode"] == "wp2_wp3"
    assert snapshot["source_wp2_stakeholder_id"] == "academic-spinout-001"
    assert snapshot["source_wp2_snapshot_version"]
    assert snapshot["source_wp3_snapshot_version"]
    assert snapshot["maturity_scores"]
    assert set(snapshot["capabilities"]) == {"federated-analytics", "legal-basis", "secure-processing"}
    assert "data-catalog" in snapshot["missing_capabilities"]
    assert "gdpr-review-needed" in snapshot["regulatory_flags"]
    assert report["recommended_path"]["trace"]["roadmap_node_ids"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_derived_readiness.py tests/test_api.py::ApiTests::test_assessment_flow_derives_readiness_without_answers_batch tests/test_d4_1_acceptance.py::test_d4_1_9_derived_assessment_uses_wp2_wp3_without_client_answers -q
```

Expected: FAIL because recommendation generation currently requires answers.

- [ ] **Step 3: Store WP2 records and derive state in service**

Modify `pathfinder/services/assessment_service.py`:

Add import near existing imports:

```python
from pathfinder.services.derived_readiness import derive_readiness_state
```

In `_load_upstream_data`, before the WP2 loop:

```python
        self.wp2_stakeholders = {}
```

Inside the WP2 loop, after duplicate check:

```python
            self.wp2_stakeholders[stakeholder_type] = dict(record)
```

In `_load_demo_data`, after appending demo-compatible types:

```python
                    "pain_points": [],
```

Add helper methods to `AssessmentService`:

```python
    def _snapshot_version(self, key: str) -> str:
        report = self.import_reports.get(key) or self.import_reports.get("upstream") or self.import_reports.get("demo")
        return report.snapshot_version if report else "unknown-snapshot"

    def _derive_state_for_session(self, session: dict[str, object]) -> dict[str, object]:
        stakeholder_type = str(session["stakeholder_type"])
        stakeholder = getattr(self, "wp2_stakeholders", {}).get(stakeholder_type)
        if stakeholder is None:
            raise ValueError(f"WP2 stakeholder record not found: {stakeholder_type}")
        state = derive_readiness_state(
            stakeholder=stakeholder,
            target_scenario=str(session["target_scenario"]),
            wp2_snapshot_version=self._snapshot_version("upstream"),
            wp3_snapshot_version=self._snapshot_version("upstream"),
        )
        session["stakeholder_state"] = state.to_dict()
        session["answers"] = state.answers
        self.audit_log.append(
            "readiness_derived",
            {
                "assessment_id": session["assessment_id"],
                "stakeholder_type": stakeholder_type,
                "derivation_mode": "wp2_wp3",
            },
        )
        return state.to_dict()

    def _state_for_recommendation(self, session: dict[str, object]) -> object:
        answers = session.get("answers")
        if isinstance(answers, dict) and answers.get("derivation_mode") != "wp2_wp3":
            return self.questionnaire_engine.build_state(
                str(session["stakeholder_type"]),
                str(session["target_scenario"]),
                answers,
            )
        state_payload = session.get("stakeholder_state")
        if not isinstance(state_payload, dict) or state_payload.get("derivation_mode") != "wp2_wp3":
            state_payload = self._derive_state_for_session(session)
        return derive_readiness_state(
            stakeholder=getattr(self, "wp2_stakeholders", {})[str(session["stakeholder_type"])],
            target_scenario=str(session["target_scenario"]),
            wp2_snapshot_version=str(state_payload.get("source_wp2_snapshot_version", "unknown-snapshot")),
            wp3_snapshot_version=str(state_payload.get("source_wp3_snapshot_version", "unknown-snapshot")),
        )
```

In `generate_recommendation`, replace answer validation/build block with:

```python
        state = self._state_for_recommendation(session)
```

In `generate_recommendation_async`, replace answer validation/build block with:

```python
        state = self._state_for_recommendation(session)
```

In `_build_report_payload`, before recommendation check:

```python
        if not isinstance(session.get("stakeholder_state"), dict):
            self._derive_state_for_session(session)
```

- [ ] **Step 4: Add report metadata fields without breaking response validation**

Modify `pathfinder/services/derived_readiness.py` so `answers` also contains top-level-like fields:

```python
        "pain_points": list(pain_points),
        "source_wp2_stakeholder_id": stakeholder_type,
        "source_wp2_snapshot_version": wp2_snapshot_version,
        "source_wp3_snapshot_version": wp3_snapshot_version,
```

Modify `_derive_state_for_session` after `payload = state.to_dict()` pattern:

```python
        payload = state.to_dict()
        payload.update({
            "derivation_mode": "wp2_wp3",
            "pain_points": list(state.answers.get("pain_points", [])),
            "source_wp2_stakeholder_id": state.answers["source_wp2_stakeholder_id"],
            "source_wp2_snapshot_version": state.answers["source_wp2_snapshot_version"],
            "source_wp3_snapshot_version": state.answers["source_wp3_snapshot_version"],
        })
        session["stakeholder_state"] = payload
        session["answers"] = state.answers
```

Modify `pathfinder/api/schemas.py` `StakeholderStateResponse`:

```python
class StakeholderStateResponse(BaseModel):
    stakeholder_type: str
    target_scenario: str
    answers: dict[str, Any]
    maturity_scores: dict[str, int]
    capabilities: list[str]
    missing_capabilities: list[str]
    regulatory_flags: list[str]
    confidence: float
    confidence_warnings: list[str]
    questionnaire_version: str
    schema_version: str
    derivation_mode: str | None = None
    pain_points: list[str] = []
    source_wp2_stakeholder_id: str | None = None
    source_wp2_snapshot_version: str | None = None
    source_wp3_snapshot_version: str | None = None
```

- [ ] **Step 5: Run backend tests**

Run:

```bash
pytest tests/test_derived_readiness.py tests/test_api.py::ApiTests::test_assessment_flow_derives_readiness_without_answers_batch tests/test_d4_1_acceptance.py::test_d4_1_9_derived_assessment_uses_wp2_wp3_without_client_answers -q
```

Expected: PASS.

- [ ] **Step 6: Run legacy compatibility tests**

Run:

```bash
pytest tests/test_api.py::ApiTests::test_assessment_flow_api tests/test_d4_1_acceptance.py::test_d4_1_5_full_api_flow_with_audit -q
```

Expected: PASS. Legacy `/answers/batch` path still works.

- [ ] **Step 7: Commit**

```bash
git add pathfinder/services/assessment_service.py pathfinder/api/schemas.py tests/test_api.py tests/test_d4_1_acceptance.py
git commit -m "feat: run recommendations from derived readiness"
```

---

### Task 3: WP2 Contract Alignment

**Files:**
- Modify: `docs/contracts/wp2_stakeholder_taxonomy.schema.json`
- Test: `tests/test_upstream.py` or new test in `tests/test_schema_normalize.py`

- [ ] **Step 1: Add schema validation test**

Add to `tests/test_schema_normalize.py`:

```python
import json
from pathlib import Path

from jsonschema import Draft202012Validator


def test_wp2_contract_accepts_capabilities_and_pain_points() -> None:
    schema = json.loads(Path("docs/contracts/wp2_stakeholder_taxonomy.schema.json").read_text())
    payload = {
        "version": "wp2-test-v1",
        "stakeholder_types": [
            {
                "id": "academic-spinout-001",
                "label": "Academic spinout",
                "personas": ["technical reviewer"],
                "user_journeys": ["prepare EHDS readiness"],
                "capabilities": ["legal-basis", "secure-processing"],
                "pain_points": ["gdpr_ehds_alignment"],
            }
        ],
    }

    Draft202012Validator(schema).validate(payload)
```

- [ ] **Step 2: Run test to verify failure or dependency gap**

Run:

```bash
pytest tests/test_schema_normalize.py::test_wp2_contract_accepts_capabilities_and_pain_points -q
```

Expected: PASS if schema allows additional properties, or FAIL if contract rejects fields. If `jsonschema` import is unavailable, use existing project validation pattern in `tests/test_schema_normalize.py`.

- [ ] **Step 3: Update WP2 schema explicitly**

Modify `docs/contracts/wp2_stakeholder_taxonomy.schema.json` inside each stakeholder item `properties`:

```json
"capabilities": {
  "type": "array",
  "items": {
    "type": "string"
  }
},
"pain_points": {
  "type": "array",
  "items": {
    "type": "string"
  }
}
```

- [ ] **Step 4: Run schema test**

Run:

```bash
pytest tests/test_schema_normalize.py::test_wp2_contract_accepts_capabilities_and_pain_points -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/contracts/wp2_stakeholder_taxonomy.schema.json tests/test_schema_normalize.py
git commit -m "docs: align WP2 contract with readiness evidence"
```

---

### Task 4: Frontend Derived Flow

**Files:**
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Update TypeScript report type**

In `frontend/src/main.tsx`, update `readiness_snapshot` type:

```ts
  readiness_snapshot?: {
    derivation_mode?: string;
    maturity_scores?: Record<string, number>;
    capabilities?: string[];
    missing_capabilities?: string[];
    regulatory_flags?: string[];
    pain_points?: string[];
    confidence?: number;
    confidence_warnings?: string[];
    source_wp2_stakeholder_id?: string;
    source_wp2_snapshot_version?: string;
    source_wp3_snapshot_version?: string;
  };
```

- [ ] **Step 2: Add small evidence component**

Add below `EvidenceList`:

```tsx
function KeyValueList({ title, values }: { title: string; values: Record<string, string | number | undefined> }) {
  return (
    <div className="evidence-block">
      <h3>{title}</h3>
      <dl>
        {Object.entries(values).map(([key, value]) => (
          <React.Fragment key={key}>
            <dt>{key}</dt>
            <dd>{value ?? "n/a"}</dd>
          </React.Fragment>
        ))}
      </dl>
    </div>
  );
}
```

- [ ] **Step 3: Render derived evidence in report**

Inside `ReportSummary`, after summary grid and before blockers:

```tsx
      <KeyValueList
        title="Derived readiness"
        values={{
          Mode: snapshot?.derivation_mode,
          "WP2 stakeholder": snapshot?.source_wp2_stakeholder_id,
          "WP2 snapshot": snapshot?.source_wp2_snapshot_version,
          "WP3 snapshot": snapshot?.source_wp3_snapshot_version,
        }}
      />
      <EvidenceList title="WP2 capabilities" items={snapshot?.capabilities} />
      <EvidenceList title="WP2 pain points" items={snapshot?.pain_points} />
      <EvidenceList title="Derived missing capabilities" items={snapshot?.missing_capabilities} />
      <EvidenceList title="Derived regulatory flags" items={snapshot?.regulatory_flags} />
```

- [ ] **Step 4: Remove answers state from normal flow**

In `App`, remove:

```ts
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
```

Remove `useEffect` that fetches `/v1/questionnaires/${stakeholderType}`.

Remove `updateAnswer` and `allAnswered`.

In `runAssessment`, replace body with:

```ts
  async function runAssessment() {
    if (!stakeholderType) return;
    setError("");
    setLoading(true);
    setReport(null);
    try {
      const session = await api<{ assessment_id: string }>("/v1/assessments", {
        method: "POST",
        body: JSON.stringify({ stakeholder_type: stakeholderType, target_scenario: "secondary-use-readiness" }),
      });
      setLastAssessmentId(session.assessment_id);
      await api(`/v1/assessments/${session.assessment_id}/recommendations?path_backend=${pathBackend}`, {
        method: "POST",
      });
      const r = await api<PathfinderReport>(`/v1/assessments/${session.assessment_id}/report`);
      setReport(r);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }
```

Change submit button:

```tsx
          <button type="button" className="submit-btn" onClick={runAssessment} disabled={!stakeholderType || loading}>
            {loading ? "Running..." : "Run derived assessment"}
          </button>
```

Replace questionnaire panel with:

```tsx
        <section className="panel">
          <h2>Derived readiness evidence</h2>
          <p className="notice">
            Readiness is derived from WP2 stakeholder capabilities and WP3 roadmap evidence.
          </p>
          <div className="evidence-block">
            <h3>Selected source</h3>
            <dl>
              <dt>Stakeholder</dt>
              <dd>{stakeholderType || "n/a"}</dd>
              <dt>Scenario</dt>
              <dd>secondary-use-readiness</dd>
            </dl>
          </div>
        </section>
```

- [ ] **Step 5: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: TypeScript + Vite build succeeds.

- [ ] **Step 6: Run frontend tests**

Run:

```bash
cd frontend && npm test
```

Expected: existing stakeholder catalog tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/main.tsx
git commit -m "feat: show derived readiness in frontend"
```

---

### Task 5: End-to-End Verification

**Files:**
- No planned source edits unless verification finds a defect.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
pytest tests/test_derived_readiness.py tests/test_api.py::ApiTests::test_assessment_flow_derives_readiness_without_answers_batch tests/test_d4_1_acceptance.py::test_d4_1_9_derived_assessment_uses_wp2_wp3_without_client_answers -q
```

Expected: PASS.

- [ ] **Step 2: Run compatibility suite**

Run:

```bash
pytest tests/test_api.py tests/test_d4_1_acceptance.py::test_d4_1_5_full_api_flow_with_audit tests/test_d4_1_acceptance.py::test_d4_1_8_fhir_export_contains_traceability_bundle -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend build/tests**

Run:

```bash
cd frontend && npm run build && npm test
```

Expected: PASS.

- [ ] **Step 4: Browser smoke**

Start dev server if none is running:

```bash
npm run dev --prefix frontend
```

Open `http://localhost` and verify:

- No `Governance readiness` slider.
- No `Known capabilities` checkbox group.
- Button says `Run derived assessment`.
- Running assessment produces report.
- Report shows `Derived readiness`, WP2 capabilities, WP2 pain points, missing capabilities, regulatory flags.

- [ ] **Step 5: Final commit if fixes were needed**

If verification required edits:

```bash
git add <changed-files>
git commit -m "fix: complete derived readiness verification"
```

If no edits were needed, do not create an empty commit.

---

## Self-Review

Spec coverage:

- Client no longer sets readiness/capabilities: Task 4.
- Backend derives readiness from WP2/WP3: Tasks 1-2.
- Solver remains deterministic: Task 2 reuses existing `PathfinderSolver`.
- Report exposes evidence/trace: Tasks 2 and 4.
- WP2 contract aligned: Task 3.
- Legacy compatibility preserved: Tasks 2 and 5.

No planned placeholders remain. Function names introduced in Task 1 are reused consistently in later tasks.

