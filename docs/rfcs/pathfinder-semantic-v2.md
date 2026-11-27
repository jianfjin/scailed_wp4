# Pathfinder semantic contracts v2

Status: proposed. Internal implementation and synthetic examples do not establish source-owner approval or authorize production cutover.

## Decision and ownership

Keep the modular monolith and immutable snapshot protocol. Introduce explicit capability evidence and three-valued conditions as a new semantic major, preserving the old contract's interpretation during migration.

| Boundary | Proposed contract | Producer / confirming parties | Approval |
| --- | --- | --- | --- |
| Questionnaire mapping | `pf.questionnaire.v2` | WP4 with WP2 content review and affected consumers | Pending |
| Rule conditions and paired tests | `pf.rulebundle.v2` | WP8 and WP4 | Pending |
| Exact-version withdrawal | `pf.withdrawal.v1` | Each source owner and WP4 consumer/operator | Pending |
| Public evidence/result projection | `/v2` service API | WP4 and supported API consumers | Pending |

Taxonomy and roadmap retain their v1 schemas. A server-owned profile selects one compatible questionnaire/rule major with those unchanged inputs. Profile identity and implementation version bind the generation, session and result; consumers cannot choose an evaluator by sending an arbitrary value.

## Contract details

- `legacy-v1` retains `pf.questionnaire.v1` and `pf.rulebundle.v1` semantics.
- `evidence-v2` requires `pf.questionnaire.v2` and `pf.rulebundle.v2`. Both use version `2.x.y` and nonempty migration notes. Unsupported or mixed semantic majors are rejected.
- A v2 capability question declares `capability_id` and the single-choice options `yes`, `no`, `unknown`. This replaces the unimplemented ambiguous `capability_maps_to` advertisement. Required-answer validation still applies.
- Selected positive multichoice items are positive self-reports; unselected items remain unknown. An explicit negative declaration is different. Contradictory claims in one answer revision are rejected.
- Findings retain judgment, answer source and verification separately. A complete questionnaire and `confidence=1` do not authenticate the claims.
- V2 rule tests add `unknown`. AND/OR/NOT preserve unknown; a potentially blocking unresolved condition produces conditional directions and missing-information descriptions. Rule import tests and runtime use the same evaluator profile.

The original v1 schemas, checksum vectors and golden samples remain intact. New sample deliveries live in `contracts/samples/v2/`, so existing v1 consumers and the default v1 sample command do not accidentally ingest another major. The directory includes unchanged taxonomy/roadmap dependencies and a separate `.notice.json` control example.

## Withdrawal control and trust

The multi-major envelope references the separate withdrawal payload schema. A withdrawal is a control message, never a snapshot eligible for runtime activation. The notice identity equals its envelope snapshot identity. Its payload lists exact `(contract, producer_wp, snapshot_id)` targets and carries a reason and source-confirmation reference.

The authorized administrator manually checks the source owner's material and attests to intake. The system records the material checksum and reference, verifies the target-list checksum and contract/producer ownership, and audits intake authorization independently. Neither a `producer_wp` string nor a material checksum independently authenticates the upstream owner. The responsible parties must approve this manual procedure before production use.

Accepted notices are append-only. Reusing an identity with different content is a conflict; repeating identical content has one effect. A trusted notice may precede the snapshot and leaves an exact-version tombstone. Its effect follows declared runtime dependencies, never `supersedes` or mere membership in a generation containing other questionnaires. Reactivation of the same snapshot cannot erase a withdrawal.

## Results and compatibility

Each result binds its answer revision, actual input snapshots and evaluation profile. Current validity is a separate observation: source withdrawal retains the original result and evidence but stops affected new recommendations. Updating answers cannot combine the old result with the new answers. Older records without recoverable original evidence remain explicitly unbound rather than receiving fabricated verification.

The v1/v2 overlap lasts one milestone or until consumers declare readiness, following `docs/15_wp_boundary_contracts.md`. Preserve historical v1 interpretation. The agreed consumer-ready cutover stops new v1 assessments/inference with an explicit migration response; a legacy projection that cannot safely express current validity must not silently present a ready plan.

## Production gates

Before cutover, obtain the confirmations above, prove migration and real PostgreSQL concurrency behavior, stop old writers, apply the versioned storage migration, start lifecycle-aware workers and verify all projections. This proposal is not a deployment instruction or evidence that those gates have passed.

## Internal implementation receipt and pending confirmation

The repository implements both registered profiles, schema-v2 persistence, guarded result publication, administrator-attested withdrawal intake and JSON/React/HTML/FHIR projections. The [cutover runbook](../runbooks/pathfinder-semantic-cutover.md) records local acceptance evidence and remaining operational gates. This does not change the pending approval states above.

Production v2 activation and new-session/answer/result writes require `PATHFINDER_SEMANTIC_V2_APPROVAL_REF` to identify the completed confirmation/readiness record; it must not be set merely because synthetic tests pass. At the approved end of overlap, all writers use `PATHFINDER_V1_WRITES_ENABLED=false`. The React v2 projection is selected explicitly by `VITE_PATHFINDER_API_VERSION=v2`.

Confirmation records must identify the responsible source and affected consumer, decision date, material reference, supported major/profile, readiness/overlap decision and withdrawal intake procedure. Ordinary subsequent content batches follow the approved interface without a fresh bilateral RFC.
