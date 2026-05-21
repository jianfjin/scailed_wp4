# T1 Second Review — Guido Gap Fixes (Arch Perspective)

**Reviewer:** Linus (Arch)
**Date:** 2026-05-21
**Reviewed Commits:** fef1303 (Guido review gaps) + 7beab2b (deferral)
**Base:** c7d9b8d
**Changed Files:** 5 files, +584 / -0 lines
**Test Suite:** 53 passed, 1 warning (pre-existing), 0 failures

**Verdict:** MERGE — all HIGH and MEDIUM gaps closed. Two nits and one fragile assertion to address before T4.2.

---

## 1. Executive Summary

The T1 fixes address all 4 HIGH-severity gaps (G1-G4) and all 3 MEDIUM-severity gaps (G5-G7) from Guido's review. The LOW gaps (G8-G10) were deferred per 7beab2b, which is the correct triage — idempotency, no-answers report, and rule-version consistency are not blocking for D4.1 demo acceptance.

The tests are well-structured, the assertions are meaningful, and the hash chain tamper tests in particular are the kind of property-based verification that catches bugs before they become audit failures. No false positives were found; every test that passes verifies what it claims to verify.

There are three items worth attention before T4.2:
- One fragile assertion in the E2E regulatory ref test (format-coupling to gen-1000-rules naming)
- One misleading code comment in the multi-pipeline test
- One weaker-than-peers assertion in `test_import_wp2_rejects_missing_label`

---

## 2. Gap-by-Gap Review

### G1: schema_version value assertion — FIXED

**Change:** `deploy/e2e_verify.py` +2 lines, `tests/test_e2e_openspec_1_5.py` +3 lines

Both the shell script and the pytest suite now assert `schema_version == "v1.0-m3-baseline"` instead of just checking presence. This is the correct fix — a system returning `"v0.1-alpha"` would previously have passed all tests. The `elif` structure in `e2e_verify.py` (check missing OR wrong value) is idiomatic and readable.

**Verdict:** Clean, minimal, correct.

### G2: Error-path tests — FIXED

**Change:** `tests/test_e2e_openspec_1_5.py` +48 lines (class `TestE2EErrorPaths`)

Two tests added:
1. `test_submit_bad_answers_returns_400` — sends `governance_maturity: "not-a-number"` (string, not int). Assertions: HTTP 400.
2. `test_recommendation_without_answers_returns_error` — creates assessment, skips answers, requests recommendation. Assertions: status != 200 AND status >= 400.

Both are real error conditions. The recommendation-without-answers test is the more important one — it validates that the service doesn't silently return an empty recommendation or crash. The double assertion (not 200 AND >= 400) is defensive against a service that returns 201 or 302 for this path.

**Minor concern:** `test_submit_bad_answers_returns_400` asserts exactly 400. If the web framework changes validation conventions (FastAPI returns 422 by default for Pydantic validation errors, not 400), this test breaks. The 400 assertion encodes an implementation detail of the current error handling. Consider testing `status >= 400` instead, or add a comment noting the 400 expectation is intentional (custom error handler).

**Verdict:** Good. Tighten the status code assertion to a range check before T4.2.

### G3: Audit event type verification — FIXED

**Change:** `tests/test_e2e_openspec_1_5.py` +83 lines (class `TestE2EAuditEventTypes`)

Three tests added:
1. `test_audit_event_types_after_full_pipeline` — set-based check that all 4 required event types exist.
2. `test_audit_event_types_exact_order` — positional check that events appear in sequence.
3. `test_multiple_assessments_produce_distinct_events` — two independent pipelines, verifies 8 events (4 per pipeline), exact order, and chain still valid.

The exact-order test indexes directly into `event_types[0..3]`. This works correctly because `AssessmentService()` in demo mode does NOT add audit events during construction (the demo data loading bypasses the audit log — confirmed experimentally). However, this is an implicit assumption. If `_load_demo_data()` is ever instrumented for audit, these index-based assertions break. Consider adding a comment or using list slicing with `startswith`-style checks.

**NIT:** The multi-pipeline test comment on line 578 says:
```python
# Pipeline 2 — use ai-factory-operator (demo data only has 2 types)
```
Demo data has 5 types (confirmed: ai-factory-operator, biotech-sme, health-data-access-body, health-data-infrastructure, research-infrastructure). The comment is stale. Fix the comment.

**Verdict:** Correct and comprehensive. Fix the stale comment.

### G4: Hash chain integrity — FIXED (BEST OF BATCH)

**Change:** `tests/test_e2e_openspec_1_5.py` +114 lines (class `TestAuditHashChainIntegrity`)

Five tests added. This is the strongest addition in the review. The tests don't just call `verify_chain()` and assert `True` — they:

1. `test_hash_chain_valid_after_normal_appends` — baseline: normal operation produces valid chain.
2. `test_prev_hash_chain_is_intact` — verifies actual hash linkage: `e2.prev_hash == e1.event_hash`. This is the key check Guido identified — without it, a system returning `audit_chain_valid=True` with broken hash links would pass. The test also validates `events[0].prev_hash is None` (genesis block).
3. `test_tampered_event_breaks_verify_chain` — sets `prev_hash` to `"00" * 32`, confirms `verify_chain()` returns False.
4. `test_event_hash_mismatch_breaks_chain` — alters `event_hash` to `"ff" * 32` while keeping `prev_hash` intact, confirms the *next* event's `prev_hash` no longer matches. This covers a different tampering vector.
5. `test_empty_chain_is_valid` — edge case: empty audit log is valid.

The tamper tests access `audit._events[1]` directly (the private list). This is fine — Python doesn't enforce access control, and testing internal state is the whole point of unit tests. The tests construct `AuditEvent` objects manually with the correct field names. I verified both tamper vectors produce `verify_chain() == False` against the actual `AuditLog` implementation.

**One observation:** `test_event_hash_mismatch_breaks_chain` keeps `prev_hash` intact and alters `event_hash`. This correctly breaks the chain because event[2]'s `prev_hash` still points to the old `event_hash` value. However, it does NOT verify that the tampered event's own computed `event_hash` would fail to match its data. The current test relies on the *next* event's link breaking, which is correct. A second tamper test that also alters `event_data` would be more comprehensive, but this is adequate for now.

**Verdict:** Rigorous. This is how audit tests should be written — property-based, covering both normal and tampered states.

### G5: Regulatory reference verification — FIXED

**Two layers of tests:**

**Unit level** (`tests/test_pathfinder_core.py` +53 lines):
- `test_regulatory_refs_propagate_into_trace` — verifies `GDPR-Review`, `EHDS-Secondary-Use`, `WP3-Roadmap` appear in trace.
- `test_regulatory_refs_empty_without_flags` — verifies empty `regulatory_flags` → empty `regulatory_refs` tuple.

Both verified against actual `AssessmentService` output. The tuple-vs-list type assertion (`assertEqual(refs, ())`) is precise and catches type mismatches.

**E2E level** (`tests/test_e2e_openspec_1_5.py` +37 lines):
- `test_trace_has_regulatory_refs` — deployed API check for `GDPR-Art.*`, `EHDS-Art.*` format with >10 refs.

**CONCERN:** The E2E test's assertions are tightly coupled to the gen-1000-rules naming convention (`GDPR-Art.25`, `AI-Act-Art.9`, `EHDS-Art.50`). These are the "real regulation references" format used in the deployed rules. If the rule format ever changes (e.g., to use `REG-GDPR-25` or `GDPR/Art.25`), this test breaks even though the system is still correct.

The unit-level test uses `GDPR-Review`, `EHDS-Secondary-Use`, `WP3-Roadmap` — the demo data format. The E2E test uses `GDPR-Art.*`, `EHDS-Art.*` — the gen-1000-rules format. Two different naming conventions in two different test layers. This is a maintenance hazard.

**Recommendation:** Add a comment documenting that the E2E assertions are format-specific to gen-1000-rules and should be updated if the rule naming convention changes. Or better: extract expected ref prefixes to a shared constant.

**Verdict:** Correct but fragile. Document the format assumption.

### G6: Fallback preserved across WP3 import — FIXED

**Change:** `tests/test_networkx_fallback.py` +44 lines

The `test_fallback_preserved_across_wp3_import` test verifies that when AGE is unavailable, importing WP3 data (which resets the graph to a new `InMemoryRoadmapGraph`) does NOT clobber `_age_unavailable` or `_graph_backend`. This maps directly to the guard at `assessment_service.py:420`:
```python
if not self._age_unavailable:
    self._graph_backend = "inmemory"
```

Without this guard, `import_wp3` would reset `_graph_backend` to `"inmemory"`, making degradation invisible to subsequent recommendations. The test covers all three relevant markers: `_age_unavailable`, `_graph_backend`, and `status().get("degraded")`.

**Verdict:** Clean. Directly tests the guard condition.

### G7: Import error tests — FIXED

**Unit level** (`tests/test_pathfinder_core.py` +67 lines, 5 tests):
- `test_import_wp2_rejects_empty_stakeholder_types` — with message check ✓
- `test_import_wp2_rejects_duplicate_stakeholder_ids` — with message check ✓
- `test_import_wp2_rejects_missing_version` — with message check ✓
- `test_import_wp2_rejects_missing_label` — WITHOUT message check ⚠
- `test_import_wp2_rejects_non_dict_entries` — with message check ✓

**API level** (`tests/test_api.py` +51 lines, 3 tests):
- `test_import_wp2_rejects_duplicate_ids_via_api` — checks HTTP 400 + VALIDATION_ERROR
- `test_import_wp2_rejects_empty_stakeholder_types_via_api` — checks HTTP 400 + VALIDATION_ERROR
- `test_import_wp2_rejects_missing_version_via_api` — checks HTTP 400 + VALIDATION_ERROR

The API-level tests are strong — they validate both the HTTP status code AND the error envelope format (`detail.error == "VALIDATION_ERROR"`). This is proper integration testing.

**NIT:** `test_import_wp2_rejects_missing_label` only uses `assertRaises(ValueError)` without checking the error message. All four sibling tests check the message. This is inconsistent. Add a message assertion:
```python
with self.assertRaises(ValueError) as ctx:
    service.import_wp2(bad_payload)
self.assertIn("label", str(ctx.exception).lower())
```

**Verdict:** Good coverage. Add the missing message assertion.

---

## 3. Code Quality Assessment

### Strengths

| Quality | Evidence |
|---|---|
| **Assertion precision** | Hash chain tests verify actual hash values, not just boolean flags. Regulatory refs test checks tuple type. |
| **Tamper coverage** | Two distinct tampering vectors tested (prev_hash alteration, event_hash alteration). |
| **Error path realism** | Both error tests exercise genuine API contract violations, not contrived edge cases. |
| **Graceful skip** | `require_docker` fixture prevents false failures; `TestAuditHashChainIntegrity` correctly has no Docker dependency. |
| **Message assertions** | 4 of 5 import error tests check the exception message, preventing false positives from unrelated ValueErrors. |
| **Test isolation** | Each test creates a fresh `AssessmentService()`, no cross-test state leakage. |

### Weaknesses

| Issue | Severity | Location |
|---|---|---|
| Fragile E2E regulatory ref format assertion | LOW | `test_e2e_openspec_1_5.py:234-242` |
| Stale comment ("demo data only has 2 types") | LOW | `test_e2e_openspec_1_5.py:578` |
| Missing error message assertion | LOW | `test_pathfinder_core.py:259-273` |
| Exact 400 assertion (should be >=400) | LOW | `test_e2e_openspec_1_5.py:274` |
| Index-based audit event assertions (brittle if constructor audited) | LOW | `test_e2e_openspec_1_5.py:546-557` |
| Setup boilerplate duplicated ~10 times | STYLE | All test files |

The duplication is the most pervasive issue but also the lowest priority — it follows the xUnit pattern of explicit Arrange-Act-Assert per test method. Refactoring to fixtures would reduce ~200 lines of duplication but is strictly a maintenance concern, not a correctness concern.

---

## 4. False Positive Analysis

I examined each new test for the specific failure mode "passes but doesn't verify what it claims":

| Test | Risk | Finding |
|---|---|---|
| `test_trace_has_regulatory_refs` | Assumes gen-1000-rules naming; could pass on wrong ref format if ref values happen to have matching prefixes | **Low risk** — the prefix assertions (`GDPR-Art.`, `EHDS-Art.`) are specific enough to catch most format mismatches. |
| `test_submit_bad_answers_returns_400` | Service could return 400 for an unrelated reason (e.g., middleware) | **Low risk** — the test creates a valid assessment first, so the 400 is explicitly from the answers endpoint. |
| `test_recommendation_without_answers_returns_error` | Service could return >=400 due to an unrelated error | **Low risk** — the preceding assessment creation succeeds, so the error is from the recommendation endpoint. If the server has a global 500, other tests would catch it. |
| `test_prev_hash_chain_is_intact` | If `verify_chain()` is a no-op returning True, the test still passes because it checks actual hash values | **No risk** — the test independently validates hash linkage, not just the verify_chain() flag. |
| `test_tampered_event_breaks_verify_chain` | If `AuditEvent` constructor ignores `prev_hash` parameter, tampering would be ineffective | **Verified** — ran manually against AuditLog implementation; tampering produces False. |
| `test_import_wp2_rejects_missing_label` | Unrelated ValueError from a different code path would cause false pass | **Low risk** — the payload is specifically crafted to have a missing label field; no other validation should trigger first. |

**No false positives found.** All tests verify what they claim to verify.

---

## 5. Deferred Gaps (G8-G10)

Per commit 7beab2b, LOW-severity gaps are deferred:

| Gap | Rationale |
|---|---|
| G8 (idempotency) | Deterministic by design (rule engine is pure function), test adds marginal value for D4.1 |
| G9 (report without answers) | Partially covered by G2's error-path test (recommendation without answers → error) |
| G10 (rule_version consistency) | Rule version is set once per import; multi-session consistency is an import-level property |

The deferral is correct. G9 is partially addressed by G2 — requesting a recommendation without answers now fails, which is the same code path that would be hit by requesting a report without answers.

---

## 6. Recommendations

### Do before merge (trivial):
1. Fix the stale comment in `test_e2e_openspec_1_5.py:578` — "demo data only has 2 types" → "demo data has 5 stakeholder types"
2. Add error message assertion to `test_import_wp2_rejects_missing_label` in `test_pathfinder_core.py:259`

### Do before T4.2:
3. Document the gen-1000-rules format assumption in `test_trace_has_regulatory_refs` or extract expected prefixes to a shared constant
4. Relax `test_submit_bad_answers_returns_400` from exact `== 400` to `>= 400` (matching the pattern used in the recommendation-without-answers test)
5. Consider refactoring the duplicated pipeline setup into a pytest fixture (low priority, maintenance hygiene)

---

## 7. Verdict

**MERGE.** All HIGH and MEDIUM gaps from Guido's review are closed with well-structured, meaningful tests. The hash chain tests in particular set the quality bar for audit verification — they test what happens when things go wrong, not just that they go right.

No blocking issues. Three LOW-severity nits that can be addressed in a follow-up commit or deferred to T4.2 hardening.

---

*— Linus (Arch)*
*SCAILED WP4 Council*
