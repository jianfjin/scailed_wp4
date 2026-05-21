# T1+T2 Joint Architecture Review

**Reviewer**: Edsger W. Dijkstra (CSO — Chief Scientific/Architecture Officer)
**Date**: 2026-05-21
**Scope**: T1 (`deploy/e2e_verify.py` + `tests/test_e2e_openspec_1_5.py`) and T2 (`pathfinder/services/assessment_service.py` + `tests/test_networkx_fallback.py`)
**Status**: Both T1 and T2 verified green (e2e_verify.py all-pass, 186 test suite green)

---

## Premise

I have been asked to review T1 and T2 together as a single system. T1 establishes the end-to-end verification pipeline: Docker health, data import, assessment creation, answer submission, recommendation generation, report export, and traceability audit. T2 introduces the degradation mechanism: when the AGE graph database is unavailable at startup, the system falls back to an in-memory graph representation and marks all outputs accordingly.

The question is not whether these pieces work in isolation — they demonstrably do. The question is whether they form a coherent whole whose correctness can be reasoned about without examining every possible execution trace. The answer, I regret to report, is no.

---

## 1. The Split-Path Problem

The most serious architectural flaw in T2 is the existence of two recommendation generation methods that exhibit different behavior with respect to degradation markers.

### 1.1 The two paths

```
generate_recommendation()           [sync]  — checks _age_unavailable, sets confidence=0.0
generate_recommendation_async()     [async] — does NOT check _age_unavailable
```

The API endpoint at `/v1/assessments/{assessment_id}/recommendations` (line 228 of `pathfinder/api/main.py`) calls `generate_recommendation_async()`. Therefore, the degradation markers — zero confidence, the `DEGRADED` warning string, the `path_backend` field — are **never applied through the API surface**. They are applied only when `generate_recommendation()` is called directly, as in the unit test `test_networkx_fallback.py`.

This is not a bug in the conventional sense. It is a failure of design discipline: the invariant "all recommendations produced under fallback shall carry confidence 0.0 and a DEGRADED warning" is enforced in one code path but not the other. The existence of two paths that purport to do the same thing but do not is the kind of duplication that breeds divergent behavior over time.

### 1.2 Correctness statement

> **Claim**: Under PATHFINDER_MODE=deployed with AGE unavailable, the `/v1/assessments/{id}/recommendations` endpoint returns confidence > 0.0.

> **Proof**: `generate_recommendation_async()` delegates to `PathfinderSolver.solve_async()`, which returns `PathResult` with `confidence=state.confidence`. The `StakeholderState.confidence` is set by `QuestionnaireEngine.build_state()`, which does not inspect `_age_unavailable`. The `build_recommendation()` function then wraps this PathResult into a dict with the original confidence. At no point in this call chain is `self._age_unavailable` consulted. QED.

### 1.3 Simplest failing test

```python
def test_fallback_degradation_through_api_path(monkeypatch):
    """The Dijkstra question: does degradation survive the recommend_async path?"""
    monkeypatch.setenv("PATHFINDER_MODE", "deployed")
    monkeypatch.setenv("PGHOST", "255.255.255.255")
    monkeypatch.setenv("PGPORT", "1")
    svc = AssessmentService(startup_check=True)

    assert svc._age_unavailable is True
    assert svc._graph_backend == "networkx_fallback"

    svc.import_wp2({
        "version": "test",
        "stakeholder_types": [{
            "id": "biotech-sme", "label": "Bio",
            "personas": ["r"], "user_journeys": ["t"],
            "feedback_categories": ["a"],
        }],
    })
    session = svc.create_session("biotech-sme", "secondary-use-readiness")
    aid = session["assessment_id"]
    svc.submit_answers(aid, {
        "governance_maturity": 2, "data_maturity": 2,
        "compliance_maturity": 2,
        "capabilities": ["secure-processing"],
        "missing_capabilities": [], "regulatory_flags": [],
    })

    import asyncio
    rec = asyncio.run(svc.generate_recommendation_async(aid))

    # THIS WILL FAIL: confidence is NOT zero through the async path
    assert rec.get("confidence") == 0.0, (
        f"async path should also zero confidence under fallback, got {rec.get('confidence')}"
    )
    assert rec.get("path_backend") == "networkx_fallback"
```

This test currently passes for `generate_recommendation()` (sync) but will **fail** for `generate_recommendation_async()`. This is the minimal witness to the correctness gap.

---

## 2. The Production Blind Spot

### 2.1 Fallback is never triggered via the API lifecycle

In `pathfinder/api/main.py`, the service is created at line 74:

```python
_service = AssessmentService(
    use_age=None,
    startup_check=False,   # <--- fallback is DISABLED
    upstream_client=_upstream_client,
)
```

The `startup_check=False` parameter means the fallback path in `AssessmentService.__init__` is never executed. The AGE connection is instead managed explicitly at lines 81-82:

```python
if _service._mode == "deployed":
    await _service.connect_age()
```

If `connect_age()` raises an exception, the lifespan context manager propagates it, and the application fails to start. There is no catch, no degradation, no fallback. The system is brittle: AGE unreachable at startup → application crash → Docker restart loop.

### 2.2 No runtime degradation

Even if the fallback were triggered at startup, there is no mechanism to detect AGE failure *after* startup. A PostgreSQL crash, network partition, or AGE extension failure occurring mid-flight leaves the system locked into whichever backend was selected at `__init__` time. Requests will fail with whatever exception the database driver raises — there is no circuit breaker, no retry, no re-degradation.

### 2.3 The `_get_service()` safety net is a trap

```python
def _get_service() -> AssessmentService:
    global _service
    if _service is None:
        _service = AssessmentService(use_age=None, startup_check=False)
    return _service
```

If the lifespan fails (e.g., `UpstreamClient.startup()` raises), `_service` remains `None`. The first API request then triggers this fallback, which constructs a fresh service with **demo data** and **no upstream client**. The application appears to work — health checks pass, endpoints return 200 — but it is serving mock data while pretending to be deployed. This is a silent degradation whose sole symptom is that `mock_data_mode` is True. No alert fires, no metric changes.

---

## 3. Semantic Drift: "NetworkX Fallback" Without NetworkX

T2 names the degradation state `"networkx_fallback"` as the `_graph_backend` value and in the `path_backend` field. However, the actual class instantiated is `InMemoryRoadmapGraph` — a pure-Python BFS implementation using `collections.deque`. NetworkX is never imported, never used.

The `InMemoryRoadmapGraph` and `AgeRoadmapGraph` classes both implement BFS identically (compare `pathfinder/core/graph.py:48-65` with `pathfinder/core/graph_age.py:278-313`). The code is duplicated. This means:

1. The "fallback" is functionally identical to "demo mode" with a different string label.
2. The name `networkx_fallback` is misleading to anyone reading logs, metrics, or the status endpoint. It suggests an external dependency (NetworkX) that does not exist.
3. If NetworkX were ever introduced as an actual fallback (e.g., for performance or algorithm correctness on large graphs), the current naming would create confusion about which mode is in use.

The correct label would be `"inmemory_fallback"` or, more honestly, `"degraded_inmemory"`.

---

## 4. Structural Coupling

### 4.1 Mode resolution is scattered

The decision of which graph backend to use is resolved from three sources in `AssessmentService.__init__`:

1. `PATHFINDER_MODE` environment variable (new)
2. `USE_AGE` environment variable (legacy, deprecated)
3. `use_age` constructor parameter (legacy, deprecated)

The precedence order is: `PATHFINDER_MODE` > `use_age` parameter > `USE_AGE` env var. This is correct but undocumented in code. Worse, `startup_check()` then overrides the backend by mutating `self.graph` and `self._graph_backend` *after* the constructor's mode resolution. The graph backend can therefore be `AgeRoadmapGraph` after line 77 but `InMemoryRoadmapGraph` after line 178. This temporal coupling makes reasoning about object state unnecessarily difficult.

### 4.2 The API layer introspects private state

`pathfinder/api/main.py` line 81 reads `_service._mode`, a private attribute, to decide whether to call `connect_age()`. This is a layering violation. The API module should not need to know the internal mode resolution logic of the service. A public method like `service.needs_age_connection()` would encapsulate this.

### 4.3 E2E tests bypass the degradation path

Both `deploy/e2e_verify.py` and `tests/test_e2e_openspec_1_5.py` test the happy path exclusively. They verify:
- Docker containers are healthy with AGE backend
- `graph_backend == "age"` in health checks
- `confidence > 0`
- `audit_chain_valid is True`

None of these tests exercises the system in a degraded state. The fallback tests live in a separate file (`test_networkx_fallback.py`) and test the service directly, not through the HTTP API. This means:

1. **The integration of T1 and T2 is untested.** No test verifies that the e2e verification script can run (and produce appropriate warnings) when the system is degraded.
2. **The API-level behavior under degradation is untested.** No test sends HTTP requests to a degraded service and verifies the response includes degradation markers.

---

## 5. Single Points of Failure

### 5.1 In-memory session state

All sessions are stored in `self.sessions: dict[str, dict[str, object]]` — an in-memory dictionary. A process restart loses all active assessments. This is acceptable for demo mode but is a structural weakness for any production deployment. The `report()` method acknowledges this at line 330:

```python
raise KeyError(f"Assessment not found: {assessment_id}. It may have expired after server restart.")
```

The error message is honest but the architecture should not depend on error messages to communicate structural limitations.

### 5.2 Audit log is append-only in memory

`AuditLog` stores events in a list with no persistence. A crash loses the entire audit chain. For a system whose core value proposition includes traceability and auditability, this is a significant gap. The hash chain provides integrity (tamper evidence) but not durability (survival across restarts).

### 5.3 Single PostgreSQL instance

In deployed mode, the entire graph state lives in a single PostgreSQL+AGE instance. There is no read replica, no connection pooling beyond `asyncpg`'s built-in pool (min=1, max=4), and no failover mechanism. The disaster recovery plan (`docs/plans/2026-05-20-disaster-recovery-plan.md`) confirms that PG backups are not yet implemented.

---

## 6. Temporal Coherence

### 6.1 Tests verify state at a point in time

Both T1 and T2 verify system behavior through sequential API calls within a single process lifetime. This works because all state is in-memory. However, it means the tests do not verify correctness across restarts, across network boundaries, or under concurrent access. The system passes because it never encounters the conditions that would expose its brittleness.

### 6.2 The demo/production boundary is blurred

The same `AssessmentService` class serves both demo mode and deployed mode, with behavior controlled by environment variables. The `mock_data_mode` flag and the `missing_data_warnings` list are always present, even in production. This is not a bug but it is a design smell: the abstraction is leaky. A deployed system should not carry demo-mode infrastructure.

---

## 7. Summary of Findings

| # | Severity | Finding |
|---|----------|---------|
| F1 | **Critical** | `generate_recommendation_async()` does not check `_age_unavailable`; degradation markers are not applied through the API |
| F2 | **Critical** | Fallback is never triggered via the API lifecycle (`startup_check=False`); AGE failure at startup causes application crash |
| F3 | **High** | No runtime degradation mechanism; AGE failure after startup is unhandled |
| F4 | **High** | `_get_service()` silently falls back to demo data if lifespan fails — production serves mock data without alerting |
| F5 | **Medium** | `"networkx_fallback"` is a misnomer; the fallback uses `InMemoryRoadmapGraph`, not NetworkX |
| F6 | **Medium** | E2E tests never exercise the degraded path; T1 and T2 integration is untested at the API level |
| F7 | **Medium** | `startup_check()` mutates `self.graph` after constructor mode resolution; temporal coupling |
| F8 | **Low** | `api/main.py` reads `_service._mode` (private attribute) — layering violation |
| F9 | **Low** | In-memory sessions and audit log are lost on restart; durability gap |

---

## 8. Recommendations

### Immediate (before any further T2 work)

1. **Add `_age_unavailable` check to `generate_recommendation_async()`.** Duplicate the degradation block from `generate_recommendation()` (lines 270-279) into `generate_recommendation_async()` after the `build_recommendation()` call. The two methods must be behaviorally equivalent with respect to degradation markers.

2. **Add an API-level degradation test.** Write a test that:
   - Sets `PATHFINDER_MODE=deployed`, `PGHOST=255.255.255.255`
   - Starts the FastAPI TestClient with `startup_check=True`
   - Makes a full pipeline request (import → create → answers → recommendations)
   - Asserts `confidence == 0.0`, `path_backend == "networkx_fallback"`, and the `DEGRADED` warning is present in the response

### Short-term (for coherence)

3. **Extract degradation logic into a private method** `_apply_degradation_markers(recommendation: dict) -> dict` called by both `generate_recommendation()` and `generate_recommendation_async()`.

4. **Enable `startup_check=True` in the API lifespan** OR catch `connect_age()` failures and trigger the fallback explicitly in the lifespan itself. The current `startup_check=False` is a conscious decision that should be documented if intentional, or fixed if accidental.

5. **Rename `"networkx_fallback"` to `"inmemory_fallback"`** to accurately reflect what is actually running.

### Medium-term (for robustness)

6. **Add a runtime health check** that periodically verifies AGE connectivity and degrades/reconnects dynamically. This could live as a background task in the FastAPI lifespan.

7. **Add a `/health` degradation test to the e2e verification suite.** The e2e script should verify that `degraded` and `degraded_reason` fields appear (or do not appear) as expected.

8. **Persist audit log events.** Even a simple append-only JSON file would provide durability across restarts for demo/deployed deployments.

---

## 9. Closing Remarks

T1 and T2 together form the skeleton of a verification + degradation architecture, but the skeleton has a broken arm. The degradation that T2 implements so carefully in the synchronous path simply does not exist in the asynchronous path that the API actually uses. This is the kind of error that arises not from carelessness but from a failure to establish and enforce a single invariant across all code paths. The duplication of the recommendation logic (sync and async variants) is the root cause; each path must independently re-implement every behavioral requirement, and one path has predictably fallen behind.

The system passes its tests because the tests do not ask the right question. The Dijkstra question — "what is the simplest failing test?" — has an answer, and that answer reveals a correctness gap that no amount of test coverage on the happy path can detect.

The remedy is not more tests. The remedy is to eliminate the duplication. There should be one recommendation generation path, with degradation markers applied at a single point. Until then, the system is correct only for the execution traces that have been tested, and incorrect for others — which is the definition of fragile software.

---

*— EWD*
