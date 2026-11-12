# WP Boundary Contracts — Design Proposal

Date: 2026-11-10

Status: Proposal for WP2/WP3/WP4/WP8 alignment (M1 schema baseline input)

Related docs:

- `docs/13_merged_pathfinder_design.md` (Determinism Contract, import/activation protocol)
- `docs/07_data_from_other_partner.md` (partner data needs)
- `docs/proposal/volume-05-api-data-specification.md` and `docs/proposal/schemas/`
- `contracts/` (the normative artifacts this document proposes)
- `scripts/validate_contracts.py` (contract CI: schema + checksum + referential rules)
- `docs/5PROPOSAL_101314097-SCAILED-EU4H-2026-SANTE-PJ-PART_B_Section_1.pdf` (Part B, the source of the WP obligations below)

## 1. Principle

Freeze the boundary, not the internals. Each work package is free to use any internal format, tool, or storage (Word, Excel, Neo4j, Notion, Python). The only binding obligation is: every artifact that crosses a work-package boundary is exchanged as a versioned JSON snapshot that validates against a published JSON Schema in `contracts/`, inside a common envelope, with stable IDs. The contract set is the interface; everything behind it is implementation detail.

Consequences:

- A WP can rewrite its internal pipeline completely without notifying others, as long as its emitted snapshots still validate.
- Machine checks cover structure, checksums, selected cross-references and executable rule examples. Content accuracy, disclosure risk and partner acceptance still require review.
- Content ownership and format ownership are separated: the owning WP owns content; the contract owns format; conflicts are resolved only through the RFC process (Section 8).

## 2. Boundary inventory

| # | Producer -> Consumer | Artifact | Contract ID |
| --- | --- | --- | --- |
| B1 | WP2 -> WP4 | Stakeholder taxonomy (types, capabilities vocabulary, personas, scenarios) | `pf.taxonomy.v1` |
| B2 | WP4 -> WP2 | Questionnaire drafts for review | `pf.questionnaire.v1` |
| B3 | WP3 -> WP4 | Roadmap graph (nodes, edges, dimensions) | `pf.roadmap.v1` |
| B4 | WP8 -> WP4 | Regulatory rule bundle (rules, references, paired rule tests) | `pf.rulebundle.v1` |
| B5 | WP4 -> WP3 | Aggregated roadmap feedback (positioning friction, blocker hotspots) | `pf.feedback.v1` (section `roadmap`) |
| B6 | WP4 -> WP8 | Aggregated rule performance (hit rates, never-fired, conflict counts) | `pf.feedback.v1` (section `rules`) |
| B7 | WP4 -> WP2 | Aggregated questionnaire signals (abandonment, ambiguity flags) | `pf.feedback.v1` (section `questionnaire`) |

WP4 is the hub: it consumes B1/B3/B4 and publishes B2/B5/B6/B7. No direct WP2<->WP3<->WP8 exchange is required for Pathfinder; they may define their own contracts separately.

## 3. The envelope

Every snapshot is one JSON document: manifest + payload. The manifest is identical across all contracts:

```text
contract        "pf.<name>.v<major>"   the contract this payload conforms to
contract_version  "1.2.0"              semver of the contract at emission time
snapshot_id       UUID                 immutable identity of this delivery
producer_wp       "WP2"|"WP3"|"WP8"|"WP4"
generated_at      RFC3339 UTC
generator         {name, version, seed|null}   reproducibility binding (ADR 0003)
supersedes        snapshot_id|null     previous snapshot this replaces
items_checksum    "sha256:<hex>"       over canonical serialisation of payload
payload           the contract-specific object
migration_notes   [{from_version, to_version, change}]  required when semantics or IDs changed
dependencies      {contract: snapshot_id}  exact versions required by this snapshot
```

`items_checksum` is SHA-256 over the UTF-8 encoding of the NFC-normalised result of `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` using Python 3. Arrays retain their emitted order: producers must choose and retain an ordering; reordering an array changes the checksum. This is a Python-defined encoding, not a claim of interoperability with arbitrary JSON serializers. See `contracts/checksum-vectors.json` for cross-language conformance vectors. The checksum identifies payload bytes, not the manifest or producer authenticity.

Each contract declares exact snapshot IDs in `dependencies`: questionnaire and roadmap depend on taxonomy; rule bundle depends on taxonomy and roadmap; feedback depends on taxonomy, questionnaire, roadmap and rule bundle. Dependencies must exist in the supplied validation set, have the stated contract and agree transitively. A historical snapshot can be supplied to validate feedback from that period.

## 4. ID namespace and stability

Format: `pf:<wp>:<type>:<slug>` where slug is lowercase `[a-z0-9-]{1,64}`.

Examples: `pf:wp3:node:governance-framework-v1`, `pf:wp8:rule:gdpr-art9-safety-clause`, `pf:wp2:stakeholder:biotech-sme`, `pf:wp8:reg:eur-lex-2016-679-art9`.

Rules:

1. IDs are forever: an ID is assigned once and never reused, even after deprecation.
2. Deprecated entities stay in the snapshot with `status: "deprecated"` (plus successor reference where one exists) for at least one major contract version; consumers must tolerate them.
3. Labels, descriptions, and metadata may change freely at the same ID; `node_id`/`rule_id`/`stakeholder_type` identity never changes. A semantic change (same ID, different meaning) requires a migration note, and is a breaking change.
4. Splitting one entity into two = new IDs + tombstones + migration note; merging = one ID retired, one kept with alias recorded.

## 5. Versioning and compatibility

Contract versions follow semver applied to the schema:

- PATCH: clarification only; schema unchanged.
- MINOR: additions inside explicitly open `metadata` objects only; consumers MUST ignore unknown metadata keys. Closed objects cannot receive a new field without breaking an old schema validator; such changes require a MAJOR unless compatibility is demonstrated for all supported consumers.
- MAJOR: breaking — removed/renamed fields, new required fields, tightened constraints, changed semantics, or ID-namespace changes. Requires a new `pf.<name>.v<N>` and a migration note in every snapshot during the overlap window.

Overlap window: after a MAJOR release, the producer must be able to emit both majors for one milestone (or until the consumer declares readiness). Each major needs its own versioned schema and fixtures; compatibility tests must exercise old consumers against new producer output. The current validator supports v1 only and does not implement this matrix yet.

Breaking changes to the roadmap graph or rule semantics additionally require the migration note mechanism already designed for Pathfinder snapshots (`docs/13`, Versioning section).

## 6. Referential rules (beyond schema validation)

Schemas cannot express cross-artifact integrity; the import validator enforces these as a second validation layer, identical rules in every WP's CI:

| Rule | Enforced on |
| --- | --- |
| Roadmap edge endpoints reference existing `node_id`s | `pf.roadmap.v1` |
| Node prerequisites reference existing nodes; edges AND prerequisites jointly acyclic (a prerequisite is a required edge) | `pf.roadmap.v1` |
| Roadmap `node.stakeholder_types` values are taxonomy stakeholder IDs or wildcard `all` | `pf.roadmap.v1` vs active `pf.taxonomy.v1` |
| Scenario `applicable_stakeholder_types` entries resolve to taxonomy stakeholder IDs | `pf.taxonomy.v1` |
| Supported stakeholder/scenario combinations (RFQ 3.2): each questionnaire's `stakeholder_type` x each `target_scenario` must appear in that scenario's `applicable_stakeholder_types` (or wildcard `all`) | `pf.questionnaire.v1` vs active `pf.taxonomy.v1` |
| Rule `applies_to` values are taxonomy stakeholder IDs or the wildcard `all` | `pf.rulebundle.v1` vs active `pf.taxonomy.v1` |
| Rule `action.node_id` references existing roadmap nodes | `pf.rulebundle.v1` vs active `pf.roadmap.v1` |
| `compliance_refs` resolve to entries of the same bundle's `references` registry; unknown refs are marked `unverified`, never rejected | `pf.rulebundle.v1` |
| Questionnaire `maturity_dimension` values are in the taxonomy `dimensions` vocabulary | `pf.questionnaire.v1` vs active `pf.taxonomy.v1` |
| Every rule has at least one paired rule test; every test's `rule_id` exists | `pf.rulebundle.v1` |
| Rule bundle tests reference questionnaire/answer constructs only via state fields declared in taxonomy/roadmap dimensions | active state contract |
| `maturity_level` is integer 1..5 everywhere it appears | all |

Referential failures reject the snapshot and must identify the exact field or contract path (import protocol, `docs/13`).

## 7. Delivery and acceptance flow

1. Producer emits `snapshot.json` into its release channel (git tag, artifact store, or the shared consortium repo folder `/snapshots/<contract>/`).
2. Both sides validate the delivery and its exact dependencies with `python3 scripts/validate_contracts.py --snapshot-dir PATH`. The directory must contain all referenced `*.snapshot.json` files; validation runs paired rule examples.
3. An administrator submits `{ "snapshots": [...] }` to `POST /v1/admin/import`, containing one taxonomy, one roadmap, one rule bundle and one or more questionnaires. The service uses the same validator and builds the complete generation before activation. In PostgreSQL mode, snapshot identity, immutable generation, active pointer and activation audit event commit in one transaction. Legacy imports are disabled in that mode.
4. Both sides run the validator in CI on every delivery and schema change; golden samples live in `contracts/samples/` and serve as fixtures and documentation.

An assessment created after activation pins the exact snapshot IDs and the UTC evaluation date; later activations do not change its questionnaire, roadmap or rules. Rules outside their effective dates are excluded and result in an unverified regulatory state. Provisional, unresolved, forthcoming or missing regulatory references also yield an unverified state; an otherwise ready result is marked `degraded`. Blocked results retain `blocked` and separately expose the unverified state.

In production, PostgreSQL stores immutable snapshot identities and generations, the active pointer, assessment sessions with their generation binding and revision, and the append-only audit chain. Workers read the active pointer from PostgreSQL; session updates use optimistic revision checks and return a conflict instead of silently overwriting concurrent work. Database failures do not fall back to process memory. Development can explicitly use the process-local `memory` mode, which does not survive restarts or coordinate workers.

### Production deployment and migration

1. Provision PostgreSQL and a durable, backed-up database. Apply the idempotent migration before starting or upgrading application workers, using an administrative migration connection:

   ```sh
   DATABASE_URL="$BOUNDARY_MIGRATION_DATABASE_URL" python scripts/migrate_boundary_storage.py
   ```

   For Compose, the equivalent is `docker compose run --rm --no-deps -e DATABASE_URL="$BOUNDARY_MIGRATION_DATABASE_URL" backend python scripts/migrate_boundary_storage.py` after PostgreSQL and the backend image are available. The migration works for existing database volumes; init scripts only run on a new volume. Startup fails if the schema version or append-only triggers are missing.
2. Grant the application role `USAGE` on schema `pf_boundary`; `SELECT` on `schema_version`; `SELECT, INSERT` on `snapshots`, `generations`, and `audit_events`; `SELECT, INSERT, UPDATE` on `active_generation` and `sessions`; and `USAGE, SELECT` on sequences in that schema. For the separate request log/dashboard, also grant `USAGE` on `assess`, `SELECT, INSERT` on `assess.request_log`, and `USAGE, SELECT` on its sequence. Keep schema ownership, migration rights, `DELETE`, `TRUNCATE`, and DDL privileges with a separate migration role. Reapply grants after future migrations if they introduce objects.
3. Set `ENVIRONMENT=production`, `DATABASE_URL` to the application role's DSN, and distinct non-empty `PATHFINDER_DEMO_TOKEN` and `PATHFINDER_ADMIN_TOKEN`. Production defaults to `BOUNDARY_STORAGE=postgres` and refuses `memory`; development defaults to `memory`. Set `CORS_ORIGINS` only when cross-origin access is needed, as a comma-separated allowlist. The frontend asks users for their access token and does not put it in report URLs.
4. Start the workers and import a validated snapshot set. Without an active generation, the service will not create a production assessment. PostgreSQL failure returns a service error rather than acknowledging a memory-only write. Existing in-memory sessions cannot be recovered or migrated automatically.

The database triggers and hash chain detect accidental mutation and protect against the restricted runtime role; they are not a digital signature against a database owner. Protect backups, administrative credentials and database access separately. Snapshot and session recovery depends on the database's backup and availability policy.

Structured delivery is the default. A WP that can only deliver narrative documents pays the boundary tax: either it writes a converter to the contract (its internals stay free), or the conversion is commissioned as option O4 work. The contract never changes to fit a document format; converters sit producer-side.

## 8. Governance

- Owners: each contract has one producer-side owner WP and one consumer (WP4 for B1/B3/B4; the respective WP for B2/B5/B6/B7).
- Changes: an RFC (short markdown PR in this repo) proposing schema + migration note + updated golden samples. Approve = both owners sign off. Disagreement escalates to the WP4 leader at the next consortium call.
- The `contracts/` directory is the single source of truth; `docs/proposal/schemas/` and the adapter code are generated from or validated against it (Phase 1 task: adapters import schema refs from `contracts/`).
- Freeze schedule: draft at kick-off, agreed baseline at M1 (schemas + golden samples), content snapshots flow continuously after M3. Schema changes after freeze only via RFC.

## 9. The contracts

Machine-readable versions (normative):

- `contracts/envelope.schema.json` — manifest + oneOf payload bindings
- `contracts/wp2-taxonomy.schema.json` — `pf.taxonomy.v1`
- `contracts/wp4-questionnaire.schema.json` — `pf.questionnaire.v1`
- `contracts/wp3-roadmap.schema.json` — `pf.roadmap.v1`
- `contracts/wp8-rulebundle.schema.json` — `pf.rulebundle.v1`
- `contracts/wp4-feedback.schema.json` — `pf.feedback.v1`
- `contracts/ids.md` — namespace rules (Section 4 copy, normative)
- `contracts/samples/*.json` — golden samples (checksum-correct, referentially valid)

The boundary format differs from the legacy import payloads. `pathfinder/adapters/boundary.py` maps a questionnaire and its taxonomy into runtime questions. `pathfinder/core/boundary_runtime.py` builds a validated generation; the legacy rule-loader test format and legacy import endpoints remain separate.

## 10. What each WP must build (minimum interface surface)

- WP2: maintain a taxonomy snapshot emitter (even a spreadsheet -> `snapshot.json` script). Review questionnaire drafts through `pf.questionnaire.v1` diffs.
- WP3: maintain roadmap graph in any tool + an exporter to `pf.roadmap.v1`. Consume `pf.feedback.v1` roadmap section.
- WP8: author rules as `pf.rulebundle.v1` (rules are data, not prose). The boundary importer executes the bundle's paired tests before activation.
- WP4: publish questionnaire and feedback snapshots, run compatibility CI, and operate the PostgreSQL migration, access controls and backups.

### Shared state and feedback

Taxonomy dimension `state_key` maps each stable dimension ID to the runtime maturity key used by roadmap `dimension` and `maturity.<key>` rule predicates. Questionnaires bind collection answers through `state_field`; capability options must occur in the taxonomy vocabulary. These bindings are demonstrated by `questionnaire_from_snapshots` and an end-to-end answer-to-rule test. Conditional question visibility remains unsupported by the current runtime and is rejected by the validator until implemented.

Feedback snapshots have one `recipient` and only that WP's section. Each published statistical row declares a distinct-subject `cohort_size` at least the threshold; nonzero counts below the threshold are omitted, and rates are held back pending disclosure review. Producers must ensure these counts represent the stated subjects. The validator cannot verify their truth or eliminate re-identification through overlapping periods, differencing or auxiliary information: WP4 must review those risks before publication.

## 11. Non-goals

- No runtime RPC between WPs; snapshots are the only cross-WP protocol in V1.
- No ontology/semantic web formats; JSON Schema only.
- No central data lake; the active snapshot set lives inside Pathfinder.
- No multilingual content contracts in V1 (English slugs + labels; `metadata` reserved for future locale maps without contract change).

## 12. Grounding in the SCAILED Part B proposal

The contracts propose machine-readable projections of Part B's narrative outputs. The manifest records sources for the snapshot as a whole; entity-level provenance requires the entity's own source reference and is not guaranteed by the manifest alone.

| Contract | Part B source | Projection |
| --- | --- | --- |
| `pf.taxonomy.v1` dimensions/stakeholders | T2.1 (identification and categorisation: segments industry/regulators/researchers/patient organisations/healthcare authorities; role classification health data holders/users; needs per group), D2.1 (M06) | stakeholder_types with `segment`, `ehds_roles`, personas with `influence`/`interest` (T2.1 items 1-2); `dimensions.positioning_axis` technical/operational/regulatory per MS4.1; wildcard "all" covers T2.1's cross-segment applicability |
| `pf.questionnaire.v1` | WP4 objectives ("we intend to receive input from WP2 (Stakeholders), WP3"), T4.1 self-evaluation tools | WP4 publishes questionnaire snapshots marked `review_status: for-review`; WP2 approves via RFC sign-off — this is the structured channel for WP2 input into WP4 content |
| `pf.roadmap.v1` nodes/edges | T3.3 ("priority applications, essential data foundations, deployment pathways, semantic interoperability ... clear responsibilities and actions for all stakeholders ... short-, medium-, and long-term actions"), WP3/MS3.1 (M16 first version), D3.2 (M36 final) | `action_type` enum = T3.3 categories; `time_horizon` = short/medium/long; `responsibility_notes` = T3.3 responsibilities; edges/prerequisites encode "pathways"; iterative MS3.1->D3.2 versions are exactly the snapshot/supersedes flow |
| `pf.roadmap.v1` datasets | T3.1.1 (characterise datasets by availability, suitability, quality, maturity, representativeness, completeness, alignment with AI Act requirements), D3.1 (M12, stakeholder-validated catalogue of high-priority datasets) | `datasets` registry with those seven attributes; nodes reference catalog entries via `dataset_refs` |
| `pf.rulebundle.v1` rules | T4.1 ("close collaboration with WP8 to make sure that the pathfinder tools are road legal"), T8.2 guideline + checklist + "possible choices and its legal consequences", T8.3.3 (compliance paths/user journeys) | eligibility/exclusion/preference/override rules with `compliance_refs`; `action.block` encodes the T8.2 checklist legal conditions |
| `pf.rulebundle.v1` references + `status` | T8.3.1 (preliminary mapping incl. forthcoming legislation e.g. Biotech Act), T8.3.2 (EHDSR interplay with AI Act, IVDR/MDR, HTAR) | `instrument` enum = those named frameworks; `status` in-force/provisional/forthcoming; `provisional` rules render Pathfinder's unverified regulatory state (RFQ 3.4), never legal conclusions |
| `pf.rulebundle.v1` tests | WP8 "conflict/priority guidance", Phase-1 validation requirement | paired rule tests per rule (also required by the import protocol, `docs/13`) |
| `pf.feedback.v1` | T4.2 test drive (LNDS AI Factory, ELIXIR + national cancer data infrastructures), D4.3 (M27 assessment of project activities), T4.3 ("revised after receiving three-fold feedback ... shared with the ancillary WPs 2, 3, 8") | aggregated node friction (B5), rule performance incl. never-fired and conflict counts (B6), question ambiguity/abandonment (B7); the minimum cohort and suppression rules reduce disclosure risk but do not establish anonymity |

Timeline fit (Part B dates): contract drafts circulated at kick-off; schema baseline agreed at M6 with D2.1 as the first projected input; first real roadmap projection at WP3/MS3.1 (M16) and D3.1/M12; rule bundle v0 from T8.2/T8.3.1 as provisional (unverified state until in-force references land); D4.1 demo at M20 runs on activated snapshots plus labelled fallbacks (docs/13 degradation rules); D3.2/M36 lands as a later roadmap content version, not a format change — the freeze in Section 5 guarantees that.

Note on milestone references: Part B numbers milestones per work package and the numbers collide (WP1/MS3.1 "Project Completed" vs WP3/MS3.1 "Initial Strategic Roadmap"; likewise MS2.1). Therefore every `derived_from` milestone carries its WP qualifier (`WP3/MS3.1`), enforced by the envelope schema pattern.

Governance in consortium terms: RFC sign-off = the "cross-WP workshops" WP1 organises for the Analyse-Implement-Test-Scale loop (Part B, section 'Enabling cross-WP alignment'); the contract test suite replaces ad-hoc format negotiations in those workshops.
