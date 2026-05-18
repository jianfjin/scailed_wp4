---
title: "feat: Council Reforms — Spec Enforcement Pipeline"
type: feat
status: active
date: 2026-05-18
council: Xuefeng, Linus, Xiaolong, Guido (4/4 consensus)
---

# feat: Council Reforms — Spec Enforcement Pipeline

## Summary

Post-mortem of the Pathfinder V1 spec drift identified 7 systemic root causes. This plan implements 5 reforms to prevent recurrence — converting manual trust into automated enforcement across the acceptance, deployment, middleware, smoke-testing, and documentation layers.

---

## Problem Frame

The Pathfinder V1 delivery (P0-P5) achieved a working 5-container pipeline but drifted from the OpenSpec/D4.1 baseline. 15 files, 1395 lines of Codex-driven fix were required to close the gap. The council's unanimous finding: the drift was not caused by human error but by systemic absence of automated spec enforcement at every layer.

---

## Council Findings (4-Seat Consensus)

| # | Root Cause | Source |
|---|-----------|--------|
| 1 | Scaffolding treated as deliverables — placeholders returned 200 OK | Linus, Xiaolong, Guido |
| 2 | Tests measured "what we wrote" not "what we promised" — P4 green ≠ D4.1 green | Xuefeng, Xiaolong |
| 3 | Cross-cutting concerns left to memory — audit/auth/rate-limit not enforced at framework level | Linus |
| 4 | Silent fallback instead of explicit failure — graph_backend degraded to inmemory without signal | Linus, Guido |
| 5 | Manual checkboxes are comfort blankets — tasks.md had no automated verification | Xuefeng, Xiaolong |
| 6 | Dual responsibility = no responsibility — local+remote both assumed the other was gatekeeping | Xuefeng |
| 7 | Deployment success ≠ integration success — containers healthy ≠ data path functional | Linus |

---

## Five Reforms

### R1. D4.1 Acceptance Test Suite (Spec → Test Mapping)

**Problem:** P4 tests covered unit logic but not D4.1 acceptance criteria. `graph_backend: "inmemory"` passed P4 because no test checked the actual backend status field.

**Solution:** Create `tests/test_d4_1_acceptance.py` with one test per D4.1 requirement. Each test fails if the requirement is not met. Tests import from the actual service, not mocks.

**Files:**
- Create: `tests/test_d4_1_acceptance.py`
- Modify: `docs/D4_1_technical_appendix.md` (add test traceability table)

**Acceptance tests:**
- D4.1.1: Five stakeholder types each have complete questionnaires
- D4.1.2: Three stakeholder/scenario fixtures produce ready recommendations
- D4.1.3: Demo rule tests match expected outcomes
- D4.1.4: Report includes readiness, path, blockers, compliance trace, warnings, disclaimer
- D4.1.5: Full API flow: create → answers → recommend → report → audit events
- D4.1.6: P95 latency at demo scale meets threshold
- D4.1.7: Docker Compose boot path verified with integration smoke

---

### R2. Startup Dependency Assertion

**Problem:** `graph_backend` silently fell back to inmemory when PostgreSQL was unreachable. `AssessmentService` accepted placeholder tokens. No component verified its dependencies at initialization.

**Solution:** Add a `startup_check()` method to `AssessmentService` that:
- Verifies PostgreSQL connectivity if `USE_AGE=1` or deployed mode
- Verifies AGE extension is loaded
- Crashes on failure with a clear error message, not silent fallback
- Runs before any API endpoint is served

**Files:**
- Modify: `pathfinder/services/assessment_service.py`
- Modify: `pathfinder/api/main.py` (call startup check in lifespan)

**Behavior change:** `graph_backend: "inmemory"` is now an explicit `--demo` flag, not a silent default. Deployed mode requires PostgreSQL or refuses to start.

---

### R3. Cross-Cutting Middleware Enforcement

**Problem:** Audit logging, token validation, and rate limiting were implemented ad-hoc per endpoint. R3 drift (missing audit events) and R4 drift (placeholder tokens) occurred because no framework-level enforcement existed.

**Solution:** Add FastAPI middleware/dependencies that apply automatically to all endpoints:

1. **Audit middleware** — All mutating endpoints (POST/PUT/DELETE) automatically append audit events. Endpoint handlers don't call `audit.log()` manually.
2. **Auth dependency** — Token validation as a FastAPI dependency injected at router level. Endpoints declare their required token level (`demo` or `admin`).
3. **Rate limit middleware** — Configurable per-endpoint rate limiting via FastAPI middleware. Default: 100 req/min for demo endpoints, 20 req/min for admin.

**Files:**
- Create: `pathfinder/api/middleware.py`
- Modify: `pathfinder/api/main.py`
- Modify: `pathfinder/core/audit.py`

---

### R4. Post-Deploy Integration Smoke Test

**Problem:** Docker Compose health checks verify process liveness, not functional integration. The 5-container pipeline could be "healthy" while `graph_backend` was disconnected.

**Solution:** Create `deploy/smoke-test.sh` — a shell script that runs after `docker compose up -d` and:
1. Verifies all 5 containers are healthy
2. Imports demo data via admin endpoint
3. Creates an assessment via public API
4. Submits answers and gets recommendations
5. Verifies `graph_backend` is `age` (not `inmemory`)
6. Checks audit events were recorded
7. Exits 0 on success, non-zero on any failure

**Files:**
- Create: `deploy/smoke-test.sh`
- Modify: `deploy/docker-compose.yml` (optional: add smoke-test service)

---

### R5. Automated Tasks.md Verification

**Problem:** `openspec/changes/add-merged-pathfinder-v1/tasks.md` checkboxes were manually maintained and diverged from reality. Without automation, humans align checkboxes at lower cost than aligning implementations.

**Solution:** Create `scripts/verify_tasks.py` — a script that:
- Reads `tasks.md` and extracts all checkbox items
- Maps each item to one or more test functions in the test suite
- Runs those tests and reports which checkboxes pass/fail
- Exits with non-zero if any checkbox claims "done" but its test fails
- Can be run in CI as a gate

**Files:**
- Create: `scripts/verify_tasks.py`
- Modify: `openspec/changes/add-merged-pathfinder-v1/tasks.md` (add test IDs)

---

## Scope Boundaries

- Do NOT introduce Kubernetes, Helm, or production CI/CD
- Do NOT add real consortium data loading
- Reforms apply to the existing demo/deployment pipeline
- All changes must pass existing P4 test suite

---

## Implementation Order

```
R1 (acceptance tests) → R2 (startup assertion) → R3 (middleware) → R4 (smoke test) → R5 (tasks verification)
```

R1 first because it defines the acceptance criteria all other reforms must satisfy.
R2+R3 together because they share the `AssessmentService` and `api/main.py` touch points.
R4 validates R1-R3 at the deployment layer.
R5 is documentation automation, dependent on R1 test IDs existing.

---

## Success Metrics

- All 7 D4.1 acceptance tests pass
- Starting backend without PostgreSQL (in deployed mode) crashes with clear error, not silent fallback
- New POST endpoint automatically gets audit logging without manual addition
- `bash deploy/smoke-test.sh` exits 0 on a healthy deployment
- `python3 scripts/verify_tasks.py` exits 0 when all tasks.md checkboxes match reality
