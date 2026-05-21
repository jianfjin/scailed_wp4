# T1 Second Review — Guido CLA Re-review of Gap Fixes

**Reviewer:** Guido van Rossum (CLA — Chief Legal/Compliance Auditor)
**Date:** 2026-05-21
**Previous Review:** `docs/reviews/t1-guido-review.md` (first review)
**Fix Commit:** `fef1303` — "test(t1): Guido review gaps — HIGH #1-#4 + MEDIUM #5-#7 resolved"
**Changed Files (5 files, +584 lines):**
- `deploy/e2e_verify.py`
- `tests/test_e2e_openspec_1_5.py`
- `tests/test_pathfinder_core.py`
- `tests/test_networkx_fallback.py`
- `tests/test_api.py`

---

## Verdict: ALL 7 GAPS CLOSED — APPROVED

Every HIGH and MEDIUM gap from my first review has been addressed with well-targeted tests. The fixes are thorough, the tests are readable, and the implementation quality matches what I'd expect from a Pythonic compliance suite. No gaps need reopening.

---

## Gap-by-Gap Verification

### G1: schema_version — Exact Value Assertion ✅ CLOSED

**Original gap:** Both scripts checked *presence* of schema_version but never asserted the value equals `"v1.0-m3-baseline"`. A system returning `"v0.1-alpha"` would pass.

**Fix applied:**
- `tests/test_e2e_openspec_1_5.py` line 169: `assert sv == "v1.0-m3-baseline"` with descriptive failure message
- `deploy/e2e_verify.py` lines 208-209: `elif schema_version != "v1.0-m3-baseline": _fail(...)`

**Assessment:** Exactly the 1-line change I recommended. The e2e verify script's `_g()` helper returns `"?"` for missing keys, and `"?" != "v1.0-m3-baseline"`, so missing values still fail. Both the pytest suite and the stdlib-only script now assert the exact value. This gap is unequivocally closed.

---

### G2: Error Paths — Negative Testing ✅ CLOSED

**Original gap:** No negative/error-path testing. Every test was a happy-path green-run.

**Fix applied:**
- `TestE2EErrorPaths` class in `tests/test_e2e_openspec_1_5.py` (lines 253-296):
  - `test_submit_bad_answers_returns_400` (line 261): Submits `governance_maturity: "not-a-number"`, asserts HTTP 400
  - `test_recommendation_without_answers_returns_error` (line 278): Creates assessment, skips answers, requests recommendation, asserts `status >= 400`

**Assessment:** Two clean, readable error-path tests. Both use the Docker skip fixture, so they integrate properly with the existing test infrastructure. 

*Minor note:* The original gap also mentioned "invalid stakeholder type" and "unauthorized access" as examples. The latter is already covered by `test_assessment_flow_requires_invited_token` (401) and `test_demo_token_cannot_use_admin_imports` (403) in `tests/test_api.py`. The "invalid stakeholder type" and "duplicate assessment" cases remain untested, but the two new tests adequately demonstrate that the system rejects malformed input rather than crashing — which was the core concern. Gap is closed.

---

### G3: Audit Event Types — Type Verification ✅ CLOSED

**Original gap:** Tests checked `audit_events >= 3` but never verified specific event types. A system emitting 3 identical events would pass.

**Fix applied:**
- `TestE2EAuditEventTypes` class in `tests/test_e2e_openspec_1_5.py` (lines 473-613):
  - `test_audit_event_types_after_full_pipeline` (line 483): Runs full pipeline via in-process `AssessmentService`, checks all 4 required types (`assessment_session_created`, `answers_submitted`, `recommendation_generated`, `report_exported`) exist in the event set
  - `test_audit_event_types_exact_order` (line 521): Verifies the exact sequence: session → answers → recommendation → report
  - `test_multiple_assessments_produce_distinct_events` (line 559): Runs two independent pipelines with different stakeholder types (`biotech-sme` + `ai-factory-operator`), verifies 8 total events in two complete sequences, and confirms `verify_chain()` remains True

**Assessment:** This goes beyond what I asked for. The exact-order test would catch a system that produces the right types but in wrong order (e.g., recommendation before answers). The distinct-pipelines test catches event cross-contamination. The in-process approach is appropriate — the deployed `/health` endpoint doesn't expose event-type granularity, so testing at the `AssessmentService` level is the right call.

*A minor architectural observation:* These tests bypass the HTTP layer entirely, so they don't verify that middleware (like `AuditWhitelistMiddleware`) correctly attaches audit events in the deployed path. The `test_audit_whitelist_warns_when_mutation_records_no_audit_event` test in `test_api.py` partially covers this concern. Not a blocker.

Gap is closed.

---

### G4: Hash Chain Integrity — Tamper Detection ✅ CLOSED

**Original gap:** Tests called `audit_chain_valid` but never validated that modifying an event actually breaks the chain.

**Fix applied:**
- `TestAuditHashChainIntegrity` class in `tests/test_e2e_openspec_1_5.py` (lines 342-466):
  - `test_hash_chain_valid_after_normal_appends` (line 348): Baseline — 3 events, `verify_chain()` returns True
  - `test_prev_hash_chain_is_intact` (line 359): Verifies each event's `prev_hash` equals the prior event's `event_hash`, and the first event's `prev_hash` is None. This checks the actual hash links — not just the top-level flag
  - `test_tampered_event_breaks_verify_chain` (line 391): Modifies event[1]'s `prev_hash` to a deliberately wrong SHA-256 value, verifies `verify_chain()` returns False
  - `test_event_hash_mismatch_breaks_chain` (line 425): Modifies event[1]'s `event_hash` while event[2]'s `prev_hash` still points to the old value, verifies `verify_chain()` returns False. This tests a different tampering vector (payload alteration)
  - `test_empty_chain_is_valid` (line 460): Edge case — empty audit log passes verification

**Assessment:** This is a thorough property test of the `AuditLog.verify_chain()` algorithm. The two tamper tests cover both tampering vectors: altering the link (`prev_hash`) and altering the payload (`event_hash`). The prev_hash integrity test adds defense-in-depth by checking the actual hash values, not just the boolean outcome.

*One observation:* The tamper tests access `audit._events[1]` — a private attribute. This is acceptable since `AuditEvent` is frozen and there's no public mutator. A comment noting the deliberate bypass would make future maintenance easier, but it's not a correctness issue.

Gap is closed.

---

### G5: Regulatory References — Compliance Citations ✅ CLOSED

**Original gap:** No verification that triggered regulatory flags propagate into the trace.

**Fix applied:**
- `test_trace_has_regulatory_refs` in `tests/test_e2e_openspec_1_5.py` (lines 208-242): E2E test that submits answers with `regulatory_flags: ["gdpr-review-needed"]` and verifies:
  - `len(refs) > 10` — the gen-1000-rules produce substantial regulatory citations
  - At least one ref starting with `"GDPR-Art."`
  - At least one ref starting with `"EHDS-Art."`
- `test_regulatory_refs_propagate_into_trace` in `tests/test_pathfinder_core.py` (lines 168-201): Unit test verifying that `GDPR-Review`, `EHDS-Secondary-Use`, and `WP3-Roadmap` appear in `trace["regulatory_refs"]`
- `test_regulatory_refs_empty_without_flags` in `tests/test_pathfinder_core.py` (lines 203-219): Verifies empty tuple when no regulatory flags are submitted

**Assessment:** The two approaches complement each other: the e2e test checks format patterns (`GDPR-Art.*`, `EHDS-Art.*`) against the deployed API, while the core tests verify the exact compliance refs from demo rules. The `len > 10` threshold is a reasonable heuristic for "real" regulatory content. The empty-flags test catches the case where a system incorrectly injects refs without input.

Gap is closed.

---

### G6: Graceful Degradation — Fallback Preservation ✅ CLOSED

**Original gap:** No test for graceful degradation mode, and no test that degradation markers survive a WP3 import (which resets the graph).

**Fix applied:**
- `test_fallback_preserved_across_wp3_import` in `tests/test_networkx_fallback.py` (lines 109-153): Forces AGE unavailable (PGHOST=255.255.255.255), imports WP3 data, verifies:
  - `_age_unavailable` remains True after import
  - `_graph_backend` remains `"networkx_fallback"` after import
  - `status["degraded"]` remains True after import
- `test_age_mode_wp3_import_updates_active_projection_without_backend_downgrade` in `tests/test_pathfinder_core.py` (lines 104-139): Verifies the non-fallback path: with `PATHFINDER_MODE=deployed` and AGE working, WP3 import correctly preserves the AGE backend

**Assessment:** The G6 fix directly addresses my concern: what happens when `import_wp3` resets the graph while the system is already in fallback mode? The answer is now tested: degradation markers survive. The complementary test in `test_pathfinder_core.py` verifies that the non-degraded path also works correctly — a system that always falls back after WP3 import would be caught.

Gap is closed.

---

### G7: Import Error Handling — Validation Rejection ✅ CLOSED

**Original gap:** No import error tests (empty stakeholder_types, duplicate IDs, missing version, invalid entries).

**Fix applied:** 8 tests total across 2 files:

*In `tests/test_pathfinder_core.py` (5 tests, lines 221-284):*
- `test_import_wp2_rejects_empty_stakeholder_types` — ValueError with "must not be empty"
- `test_import_wp2_rejects_duplicate_stakeholder_ids` — ValueError with "duplicate stakeholder type"
- `test_import_wp2_rejects_missing_version` — ValueError with "version"
- `test_import_wp2_rejects_missing_label` — ValueError raised
- `test_import_wp2_rejects_non_dict_entries` — ValueError with "must be objects"

*In `tests/test_api.py` (3 tests, lines 261-310):*
- `test_import_wp2_rejects_duplicate_ids_via_api` — HTTP 400, VALIDATION_ERROR
- `test_import_wp2_rejects_empty_stakeholder_types_via_api` — HTTP 400, VALIDATION_ERROR
- `test_import_wp2_rejects_missing_version_via_api` — HTTP 400, VALIDATION_ERROR

**Assessment:** The tests cover the three error categories from my original gap (empty types, duplicate IDs, missing version) at both the service layer (ValueError) and the API layer (HTTP 400). The missing_label and non_dict tests go beyond what I asked for — a nice demonstration of defensive validation. The API tests consistently return `VALIDATION_ERROR` detail, which gives frontend developers a clear error contract.

Gap is closed.

---

## Overall Quality Assessment

### What Improved

1. **Depth of verification:** We went from "presence checks" to "correctness checks." Schema version is now exact-matched, audit events are type-verified in order, and the hash chain is tested for tamper resistance — not just a pass/fail flag.

2. **Separation of concerns:** The new tests are cleanly organized into focused classes (`TestE2EErrorPaths`, `TestAuditHashChainIntegrity`, `TestE2EAuditEventTypes`). Each class has a clear purpose and doesn't intermix concerns.

3. **Dual-layer testing:** Where possible, fixes include both in-process/core tests and API-level tests (G5, G7). This gives confidence that the logic works and the HTTP contract is correct.

4. **Readable assertions:** The error messages in assertions are descriptive (e.g., `f"Missing required audit event types: {missing}. Found types: {sorted(event_types)}"`). This is Pythonic — debugging a test failure should not require reading the test source.

### Remaining Observations (not blockers)

These are items from my first review that were LOW severity (G8-G10) or architectural notes. They are not part of the 7-gap fix scope and do not block approval:

| # | Item | Severity | Status |
|---|---|---|---|
| G8 | Idempotency test (same assessment, two recommendations) | LOW | Deferred per `docs/dr/non-blocking-dispositions.md` |
| G9 | Report without answers test | LOW | Partially addressed by G2's recommendation-without-answers test; report-without-answers remains untested |
| G10 | Rule version consistency across assessments | LOW | Deferred |
| — | Code duplication in traceability tests (3 tests each run the same 4-step pipeline) | Style | The G3/G4 new tests avoid this by using in-process service calls. The original traceability tests still duplicate the pipeline. A shared fixture would be nice but is not a correctness issue. |
| — | In-memory audit log (lost on restart) | Architectural | Noted in first review §4.1. Acceptable for demo. Production persistence is a T4.2 concern. |

---

## Recommendation

**APPROVED.** All 7 gaps (G1-G7) are properly closed. The T1 test suite now meets the bar for stakeholder review sessions (OpenSpec 4.3). The remaining LOW-severity items (G8-G10) are correctly deferred per the non-blocking dispositions record.

The fixes demonstrate attention to both the letter and spirit of my original review. The hash chain tamper tests in particular show an understanding that compliance verification isn't about checking a boolean — it's about proving the boolean means what it claims.

---

*— Guido van Rossum, CLA*
*Chief Legal/Compliance Auditor, SCAILED WP4 Council*
