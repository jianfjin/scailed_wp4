---
title: "Audit: Council Reform Plan — Spec Enforcement Pipeline"
type: audit
date: 2026-05-18
auditors: Xuefeng, Linus, Guido, Xiaolong (4/4)
verdict: CONDITIONAL PASS — 16 findings, 3 blocking conditions
---

# Audit: Council Reform Plan

## Verdict

**CONDITIONAL PASS (4/4)** — Plan is directionally correct. Five reforms address 6 of 7 root causes. Three conditions must be met before implementation proceeds.

## Auditor Votes

| Auditor | Vote | Blocking Issues |
|---------|------|----------------|
| Xuefeng | Conditional Pass | Missing R6 (accountability), R5 gap detection, Makefile CI target |
| Linus | Conditional Pass | C1: gate ownership, C2: default-deny auth, C3: test ID annotations |
| Guido | Conditional Pass | Audit middleware redesign, demote R5, Python smoke test |
| Xiaolong | Conditional Pass | conftest.py for tests, audit middleware downgrade, 2-PR split |

---

## Consolidated Findings

### Blocking Issues (Must Fix Before Implementation)

**B1. Root Cause 6 Uncovered — Dual Responsibility (All 4 auditors)**

The 7th root cause — "local+remote both thought the other was gatekeeping" — is not addressed by any reform. Five reforms automate enforcement of 6 root causes, but the human accountability gap remains.

**Fix:** Add an explicit governance clause to the plan: "CI smoke test is the sole acceptance gate. If `deploy/smoke_test.py` fails, the PR does not merge. No human override." This eliminates the coordination gap by making the gate machine-enforced.

**B2. R3 Audit Middleware Over-Abstracted (Guido, Xiaolong)**

The plan states "handlers don't call audit.log() manually — middleware handles it." But domain audit events (e.g., "assessment_session_created") rely on business context that HTTP middleware cannot infer. If middleware auto-generates events, they degrade to generic "POST /path" entries. If middleware parses response bodies, it couples to business schemas.

**Fix (Guido+Xiaolong compromise):** Downgrade R3 audit to a **whitelist checker**: middleware verifies that every POST/PUT/DELETE handler produced at least one audit event. If `audit_events == 0` after handler returns, emit a WARNING. Handlers still call `audit.append()` explicitly, but middleware ensures they don't forget.

**B3. R5 Two-Source-Of-Truth Risk (Guido, Linus)**

Maintaining both `tasks.md` checkboxes AND test annotations creates two sources of truth that can drift apart. The R5 design risks becoming "another comfort blanket."

**Fix (Guido+Linus compromise):** 
- Demote R5 from CI gate to informational report
- OR merge R5 into R1: each D4.1 test prints the spec clause it validates
- If R5 survives: use explicit `(test: module.Class.test)` annotations in tasks.md, as Linus specified

---

### Implementation-Level Gaps (Fix During Development)

**G1. R2 Breaks All Existing Tests (Xiaolong)**

`AssessmentService()` currently defaults to inmemory mode. Making PostgreSQL mandatory breaks test_api.py, test_acceptance_baseline.py, test_pathfinder_core.py.

**Fix:** 
- Add `AssessmentService(startup_check: bool = True)` parameter (default True for deployed mode)
- Create `tests/conftest.py` with `AssessmentService(startup_check=False)` fixture
- Use `PATHFINDER_MODE=demo|deployed` env var (Linus), not `--demo` CLI flag

**G2. R4 Smoke Test Should Be Python, Not Bash (Xiaolong, Guido)**

A bash script with `curl | grep | jq` is fragile. Field name changes cause silent failures.

**Fix:** Write `deploy/smoke_test.py` using Python requests/urllib. Each step in try/except with clear failure messages. Shell wrapper: `smoke-test.sh` calls `docker compose exec backend python smoke_test.py`.

**G3. D4.1.6 Latency Should Not Be a CI Gate (Guido)**

P95 latency thresholds on CI runners (variable hardware) produce flaky gates.

**Fix:** Make D4.1.6 an informational benchmark, not a hard CI gate. Gate only on functional correctness.

**G4. D4.1.5 and D4.1.7 Have Hidden Dependencies (Linus)**

D4.1.5 (audit events) depends on R3. D4.1.7 (Docker boot) depends on R4. These tests will RED before their dependency reforms are implemented — which is correct TDD behavior, but should be documented to prevent confusion.

**Fix:** Tag these tests with `@pytest.mark.skip(reason="Requires R3")` and `@pytest.mark.skip(reason="Requires R4")` until dependencies are implemented.

---

### Nice-to-Have (Implement If Time Permits)

**N1. Makefile CI Target (Xuefeng, Xiaolong)**

```makefile
.PHONY: ci
ci: test smoke-test verify-tasks
```
A single `make ci` that a developer runs before pushing. No CI/CD server needed — the Makefile IS the CI.

**N2. 2-PR Split (Xiaolong)**

PR1 = R1 + R2 + R3 (core code + tests, highest risk)
PR2 = R4 + R5 (deployment verification + docs, no side effects)

**N3. Rate Limit Simplification (Xuefeng)**

Use one default rate limit (100 req/min) with per-endpoint exceptions, not a full per-endpoint configuration matrix.

---

## Coverage Matrix (Post-Fix)

| Root Cause | R1 | R2 | R3 | R4 | R5 | R6 (new) | Status |
|-----------|:--:|:--:|:--:|:--:|:--:|:--------:|--------|
| RC1 Scaffolding as deliverables | ✓ | ✓ | ✓ | - | - | - | Covered |
| RC2 Tests measured implementation, not spec | ✓ | - | - | - | ✓ | - | Covered |
| RC3 Cross-cutting concerns ad-hoc | - | - | ✓ | - | - | - | Covered |
| RC4 Silent fallback instead of explicit failure | - | ✓ | - | ✓ | - | - | Covered |
| RC5 Manual checkboxes = comfort blanket | ✓ | - | - | - | ✓ | - | Covered |
| RC6 Dual responsibility = no responsibility | - | - | - | ✓ | - | ✓ | **NOW COVERED** |
| RC7 Containers healthy ≠ data path healthy | - | - | - | ✓ | - | - | Covered |

---

## Revised Implementation Order

```
Phase 1: R1 (acceptance tests) — define failing tests first
Phase 2: R2 + R3 (startup assertion + middleware) — shared touchpoints in AssessmentService + main.py
Phase 3: R4 (smoke test) — deploy/docker compose exec smoke_test.py
Phase 4: R5 (tasks verification) — informational script, not gate
Phase 5: R6 (governance clause) — single sentence in D4.1 appendix
```

All phases pass existing P4 tests. R2 uses conftest.py to preserve test backwards compatibility.
