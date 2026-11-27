# Pathfinder semantic v2 cutover

Status: internal implementation verified; production cutover has not been performed. The affected-WP RFC and consumer readiness confirmations remain pending. This document authorizes no production operation by itself.

## Release gates

| Gate | Evidence / required action | State |
| --- | --- | --- |
| Shared semantics | Record WP4/WP2 questionnaire confirmation, WP8/WP4 rules confirmation, each source-owner withdrawal procedure and affected consumer readiness in [the RFC](../rfcs/pathfinder-semantic-v2.md). Preserve one milestone of overlap or documented consumer readiness. | Pending external confirmation |
| Persistent enforcement | Isolated PostgreSQL 16: schema v1→v2, immutable history, least privilege, cross-process visibility, warm/restarted workers, controlled competing commits and audit-failure rollback. | Local acceptance passed |
| Controlled rollout | Stop every old writer, migrate, start only lifecycle-aware workers, verify projections, then reopen writes. | Production not executed |

Synthetic sample references, a notice checksum, an administrator token and the approval configuration below are not independent proof of source-owner approval.

## Compatibility and operation

| Consumer | During overlap | At the approved cutover |
| --- | --- | --- |
| `/v1` | Original `legacy-v1` profile; existing historical interpretation retained. | `PATHFINDER_V1_WRITES_ENABLED=false` rejects new sessions, answers and inference with `409 MIGRATION_REQUIRED`. |
| `/v2` | `evidence-v2` assessments with capability findings, conditional directions and explicit validity. | Continue using the approved exact input versions. |
| Historical results | `GET /v2/assessments/{id}/report?result_id=...` preserves original answers and output. | Withdrawal changes the current validity overlay, never the stored output or content hash. |
| Legacy evidence not recoverable | Migration preserves the result as `legacy_unbound`, with original answer binding unknown and a nullable readiness snapshot. | Do not copy current answers into the old result. Reassessment under new semantics uses a new session. |
| Old projections | Unsafe withdrawn or unbound projections return a migration conflict. | Use the explicit evidence/validity reader; do not discard new fields and show ready. |
| Feedback | Existing `pf.feedback.v1` retains its original meaning. | Do not aggregate v2 unknown as false/not-triggered; new metrics need a separate agreement. |

`GET /v2/assessments/{id}` exposes `result_history` identities, including migrated records. `result_id` may select a historical result belonging to that assessment. Unbound historical reports show original evidence as unavailable; they never substitute current answers. FHIR requires recoverable original answers and returns a migration conflict for these records. Without it, v2 reports require a result for the current `answer_revision`, including when reading a legacy session; otherwise they return `409 RECOMMENDATION_REQUIRED`, without computing a result on read. v1 implicit report computation still uses the guarded publication operation.

The React client defaults to explicitly labelled v1. Build or start it with `VITE_PATHFINDER_API_VERSION=v2` to use the v2 routes. Both development proxy prefixes are configured. There is no fallback to legacy evaluation when a v2 request fails.

## Before maintenance

1. Obtain the RFC confirmations and record the consumer-ready cutover decision. Keep the actual materials in the agreed source-owner system.
2. Inventory every worker, CLI and background process that can write assessments or activate inputs. Stop all old writers before migration; a rolling deployment with old writers remaining is not supported.
3. Take and verify the normal database backup. Rehearse restoration in an isolated environment. Use a migration account with DDL authority and an existing separate runtime role.
4. Keep the runtime write path closed until migration and smoke verification complete. Do not point the tests below at production.

## Migrate and start

Use the deployed Python environment and supply `DATABASE_URL` through the approved secret mechanism. Do not print the connection string in logs.

```sh
python3 scripts/migrate_boundary_storage.py --schema pf_boundary --runtime-role pathfinder_runtime
```

The idempotent migration installs schema version 2, append-only withdrawal targets and results, and independent active-generation pointers per profile. It maps the old active pointer to `legacy-v1`. Existing snapshot JSON values, canonical hashes and original result values are preserved; raw JSON whitespace and key order were never a stored contract.

The runtime role receives schema usage, table reads/appends, session/pointer updates and sequence access. It does not need schema ownership or DDL. Startup checks version, tables, append-only triggers, required table privileges and the audit chain. Missing migration or permissions must be corrected while writes remain closed.

Start only the new lifecycle-aware workers. In production, v2 activation and new session, answer and result writes are disabled unless `PATHFINDER_SEMANTIC_V2_APPROVAL_REF` names the completed RFC/consumer-readiness record. Set this only after the real confirmations exist. A previously stored active pointer does not bypass this check. Keep both profiles' pointers during the overlap; do not infer profile from the largest version number.

At the approved end of the overlap set `PATHFINDER_V1_WRITES_ENABLED=false` consistently on all writers. This does not delete historical results.

## Acceptance before reopening writes

```sh
python3 scripts/validate_contracts.py
python3 scripts/validate_contracts.py --snapshot-dir contracts/samples/v2
python3 -m pytest tests/test_boundary_postgres.py -q
python3 scripts/build_openapi.py --check
npm --prefix frontend test
npm --prefix frontend run build
```

Configure `TEST_BOUNDARY_DATABASE_URL` for a dedicated isolated PostgreSQL instance when running persistence tests. A skipped database test does not satisfy this gate. The separate `.notice.json` sample is a control message and is not part of runtime snapshot activation.

Exercise yes/no/unknown, complete self-report remaining unverified, changing answers after a result, selecting the earlier result, withdrawal before target arrival, withdrawal during computation and a withdrawal affecting only one of two questionnaires. The unaffected questionnaire must continue to work in warm and restarted workers. Confirm that failed publication appends neither a successful result nor a success audit.

Check the same selected result through JSON, React, HTML and FHIR. FHIR conditional guidance is data-required/draft; known blocked evaluation succeeds without an executable plan; regulatory-only degradation succeeds with a draft and warning; withdrawn unexecuted historical plans are revoked. A session marked complete does not establish plan execution. Legacy blocked CarePlan envelopes remain draft during overlap; v2 omits the plan.

The repository `make gate` also requires its Docker Compose smoke/restore environment and task-verification prerequisites. Do not interpret missing backups, unavailable Docker services or skipped checks as release success.

## Local implementation evidence — 2026-11-27

- Targeted domain, lifecycle, real PostgreSQL, API/OpenAPI, HTML and FHIR acceptance: 281 passed, with no skips in the persistence group.
- Frontend: eight Node tests and the production build passed.
- Real desktop/mobile browser: conditional direction, unverified self-report, blocked direction, draft-edit clearing and withdrawn historical views passed. The HTML, JSON and FHIR checks used the same original result/answers and lifecycle observation; no console errors or horizontal overflow were observed. Additional delayed-response checks verify that clearing the token cannot restore a previous connection's profiles or results.
- Full suite: 385 passed, 21 failed, 34 skipped. A clean `147536a` baseline in the same environment produced 296 passed, 23 failed, 34 skipped. No new failures remained. Existing failures concern mock-data expectations, removed AGE fallback assumptions and unavailable backup/restore integration prerequisites; the two prior FHIR fixture failures no longer occur.
- The local verification files and browser captures are retained in the execution journal, outside the source tree. This is implementation evidence, not production or source-owner approval.

## Review coverage

The dedicated automated review was interrupted by a tool usage limit before a completed review receipt. Its available findings, independently reproduced failures and the final diff received local review. Nineteen additional regression cases cover invalid inputs, optional answers, production gates, migrated historical reads and independent result bindings; guard-removal checks verify that the relevant protections fail their tests when removed. A completed independent review remains an approval prerequisite; this delivery is a draft.

## Failure and rollback

If migration or verification fails, leave writes closed. Restore through the established backup procedure when necessary, then retry only after diagnosing the failure. Never start an older binary that can write without checking withdrawals or answer revisions. Prefer a forward fix or a rollback build that still understands schema v2 and enforces the same lifecycle constraints.

An accepted notice cannot be cleared by reactivating the same snapshot. A replacement uses a new exact identity and valid dependencies; `supersedes` records lineage and does not itself inherit the old version's withdrawal.
