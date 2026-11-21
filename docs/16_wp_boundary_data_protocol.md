# SCAILED Pathfinder — Work-Package Boundary Data Protocol

| | |
| --- | --- |
| Status | **Version 1.0 — freeze candidate** (Rev3) |
| Date | 11 November 2026 |
| Owners | WP4 (consumer of record); producer owners per contract, Section 11 |
| Binding on | WP2, WP3, WP4, WP8 development teams |
| Machine-readable source of truth | `contracts/` in this repository; this document is the human-readable normative companion |
| Validation command | `python3 scripts/validate_contracts.py` (same code runs in Pathfinder at import time) |

---

## 1. Purpose and scope

This protocol fixes the data that crosses the boundaries between the SCAILED Pathfinder work packages WP2 (stakeholder analysis), WP3 (strategic roadmap), WP4 (pathfinder toolkit — the Pathfinder service itself) and WP8 (legal and regulatory alignment). It defines:

1. one **snapshot format** (Section 3) used for every cross-WP hand-off;
2. five **contracts** (Section 5), one per boundary artefact, each with a JSON Schema, ID vocabulary and referential rules;
3. four **validation gates** (Section 7) that every delivery must pass before activation;
4. the **delivery, activation and version-pinning flow** (Section 8) and the production runtime requirements (Section 9);
5. the **governance** for changing any of the above after freeze (Section 10).

It does **not** constrain anything inside a work package. How WP3 stores its roadmap, which language WP8 uses to author rules, or how WP2 interviews stakeholders are all internal concerns. A WP is compliant with this protocol if and only if the snapshot(s) it publishes validate against the contract named for its boundary.

**Why this matters for the project:** Pathfinder's recommendations must be reproducible and traceable (RFQ requirements F07/F08, ADR 0003). That is only possible if the inputs arriving from WP2/WP3/WP8 are content-addressed, versioned artefacts rather than e-mailed documents. This protocol is what turns "the roadmap" into "the roadmap snapshot with a checksum, an ID and a dependency closure".

## 2. Normative principles

The language of this document is RFC 2119-style: **MUST** (binding), **SHOULD** (strong default, deviations are recorded), **MAY** (optional).

1. **Freeze the boundary, not the interiors.** Only the artefacts defined here are binding.
2. **A snapshot is the only delivery vehicle between WPs.** Reports (Part B deliverables D2.1, D3.1, D3.2, D8.x) remain the narrative deliverables; every cross-WP object inside them MUST also exist, in machine-readable form, as a snapshot projection. The `manifest.derived_from` field binds each projection to its source deliverable.
3. **Machine-checkable or it did not happen.** The single arbiter of compliance is `scripts/validate_contracts.py`. A meeting decision that contradicts a failing validator is not a decision.
4. **IDs are forever; labels are free.** See Section 4.
5. **Dependencies are explicit.** Every snapshot names the exact snapshot IDs it was built against (Section 3.2). "Latest" is never a semantic.
6. **One validator implementation.** The rules below execute from `pathfinder/core/boundary_validation.py` in three places: your CI, our CI, and Pathfinder's import path. There is no second dialect.

## 3. The snapshot format (envelope)

Every delivery is one JSON document:

```json
{
  "contract": "pf.roadmap.v1",
  "manifest": { ... },
  "payload": { ... }
}
```

`contract` MUST be one of the five names in Section 5 (closed enum — unknown or future version strings are rejected, not ignored). Each contract name is bound to exactly one producer work package; a WP8 rule bundle claiming `producer_wp: "WP4"` is rejected at Gate 1.

### 3.1 Manifest fields

The manifest is identical across all contracts. Required fields:

| Field | Type | Rules |
| --- | --- | --- |
| `contract_version` | semver string | version of the contract **at emission time** (`1.0.0`) |
| `snapshot_id` | UUID | immutable identity of this delivery; checked as a real UUID by the validator |
| `producer_wp` | `"WP2"` \| `"WP3"` \| `"WP4"` \| `"WP8"` | must match the `contract` binding |
| `generated_at` | RFC 3339 UTC timestamp | deterministic generators pin this value |
| `generator` | `{name, version, seed?}` | reproducibility binding (ADR 0003); `seed` present whenever output is generated |
| `items_checksum` | `"sha256:<64 hex>"` | over the canonical serialisation of `payload` — Section 3.3 |
| `derived_from` | array, min 1 | the Part B objects this payload projects: `source` (e.g. `D3.1`, `T8.3.1`, `WP3/MS3.1`), optional `section`, `status` ∈ `approved`/`draft`/`forthcoming` |
| `dependencies` | object | Section 3.2 — contract name → required snapshot UUID |

Optional fields:

| Field | Rules |
| --- | --- |
| `supersedes` | `snapshot_id` of the previous delivery this replaces; self-reference rejected. The newest link of a supersedes chain is the **active** snapshot |
| `migration_notes` | array of `{from_version, to_version, change}` — **required content** whenever the payload's semantics or IDs changed (major evolution, Section 10) |

`derived_from.source` milestone references MUST carry the WP qualifier (`WP3/MS3.1`), because Part B milestone numbering collides across work packages (WP1/MS3.1 = "Project Completed", WP3/MS3.1 = "Initial Strategic Roadmap").

### 3.2 Dependency pinning

Each contract declares which other contracts' exact snapshots it was built against:

| Contract | dependencies |
| --- | --- |
| `pf.taxonomy.v1` | (none — root) |
| `pf.questionnaire.v1` | taxonomy |
| `pf.roadmap.v1` | taxonomy |
| `pf.rulebundle.v1` | taxonomy, roadmap |
| `pf.feedback.v1` | taxonomy, questionnaire, roadmap, rule bundle |

Every referenced snapshot MUST exist in the same validation set, MUST carry the stated contract name, and the closure MUST resolve transitively with consistent IDs. Consequences you can rely on:

- validating a feedback window from Q4 2026 does not require today's taxonomy — you ship the taxonomy snapshot of that period and the set validates;
- an activation is a **generation**: the complete, dependency-closed set of snapshots Pathfinder runs against;
- a `dependencies` entry pointing at a snapshot that is not the active head of its supersedes chain is legal (historical validation) but Pathfinder only ever activates complete current generations.

### 3.3 Checksum definition

`items_checksum = "sha256:" + SHA256( NFC( json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) ).encode("utf-8") )`

evaluated with CPython 3. This is deliberately a **Python-defined encoding**, not a claim that arbitrary JSON serialisers agree. Notes:

- **Arrays keep their emitted order.** Re-ordering an array changes the checksum; producers MUST choose an order (e.g. sort by ID) and keep it.
- **NFC normalisation** means `Café` composed and decomposed (U+00E9 vs U+0065 U+0301) produce the same checksum.
- Three conformance vectors live in `contracts/checksum-vectors.json` (`unicode-nfd`, `numeric-and-order`, `escaped`). Any non-Python emitter MUST reproduce them before production traffic.
- The checksum identifies **payload bytes only**. It is not a signature: it does not attest producer authenticity or manifest integrity. Trust comes from the release channel (Section 8) and the audit chain (Section 9).

## 4. ID namespace and stability

All cross-boundary identifiers: `pf:<wp>:<type>:<slug>` where `<wp>` ∈ wp2/wp3/wp4/wp8, `<type>` names the entity kind (`node`, `rule`, `question`, `reg`, `scenario`, …) and `<slug>` matches `[a-z0-9-]{1,64}`.

Stability rules (binding):

1. An ID is assigned **once and never reused**, including after deprecation.
2. Deprecated entities stay visible with `status: "deprecated"` plus `successor` (ID or null) for at least one major contract version.
3. Labels, descriptions and metadata may change at constant ID; identity never changes. **A semantic change at the same ID is a breaking change** requiring `migration_notes`.
4. Split = new IDs + tombstone on the old. Merge = retire one, keep one, record the retired ID in `metadata.id_aliases`.

Fields named `*_type`, `applicable_*`, `applies_to` accept either such an ID or the wildcard `"all"`. Fields `prerequisites`, `compliance_refs`, `dataset_refs` are ID-only — a wildcard there is meaningless and rejected.

## 5. The contracts

Field tables list `name: type [* = required]`. `ref` = ID pattern from the contract's `$defs`.

### 5.1 `pf.taxonomy.v1` — WP2 → everyone

Source: Part B T2.1, D2.1 (M06); positioning axes from WP4/MS4.1. Producer owner: WP2. The root of every dependency closure.

Payload: `dimensions[]`, `stakeholder_types[]`, `scenarios[]`, `capability_vocabulary[]` (all four required).

| dimensions | |
| --- | --- |
| `dimension_id: ref` \* | `pf:wp2:dimension:<slug>` |
| `label` \*, `state_key` \* | `state_key` ∈ governance, data, compliance, infrastructure, capability — the maturity namespace this dimension feeds |
| `positioning_axis` \* | technical \| operational \| regulatory (MS4.1 wording) |
| `scale` | `{min: 1, max: 5}` when present |

| stakeholder_types | |
| --- | --- |
| `stakeholder_type_id: ref` \* | `pf:wp2:stakeholder:<slug>` |
| `label` \*, `status` \* | status ∈ active, deprecated; `successor` nullable ID |
| `ehds_roles` \* | min 1 of: data-holder, data-user, intermediary, regulator, developer (T2.1 role classification) |
| `segment` | free string — T2.1 categories (industry, regulators, researchers, patient organisations, healthcare authorities, …). Open vocabulary; expect an RFC to enum-ify it with an extension mechanism |
| `capabilities` | entries SHOULD come from `capability_vocabulary` |
| `personas[]` | `{persona_id, label, influence, interest}` with influence/interest ∈ low, medium, high (T2.1 influence/interest mapping) |

| scenarios | |
| --- | --- |
| `scenario_id: ref` \* | `pf:wp2:scenario:<slug>` |
| `label` \*, `applicable_stakeholder_types` \* | every entry MUST resolve to an existing stakeholder ID (or `all`) |
| `target_description` | free text |

`capability_vocabulary: string[]` — the closed set of capability tokens that questionnaires may map to and rule conditions may test against. Introduce a token here **before** referencing it anywhere else.

### 5.2 `pf.roadmap.v1` — WP3 → Pathfinder

Source: T3.3 (actions, categories, horizons, responsibilities), D3.1 (M12 dataset catalogue), WP3/MS3.1 (M16) and D3.2 (M36) as successive projections. Producer owner: WP3.

Payload: `nodes[]` and `edges[]` required; `datasets[]` carries the D3.1 catalogue.

| nodes | |
| --- | --- |
| `node_id: ref` \* | `pf:wp3:node:<slug>` |
| `label` \*, `dimension` \*, `maturity_level: int 1–5` \* | dimension ∈ the five `state_key` values; maturity = position on that dimension's 1..5 scale |
| `stakeholder_types` \* | IDs or `all`; every entry MUST exist in the active taxonomy |
| `prerequisites` \* | node IDs; jointly acyclic with edges (Section 6) |
| `source_wp: "WP3"` \*, `source_doc_ref` \*, `confidence: 0–1` \* | `source_doc_ref` names the Part B passage; confidence records evidence strength (D3.2's iterative nature) |
| `action_type` | priority_application, data_foundation, deployment_pathway, semantic_interoperability, governance_action, infrastructure_provision — the six T3.3 categories |
| `time_horizon` | short \| medium \| long (T3.3) |
| `responsibility_notes: array` | "clear responsibilities" per T3.3 |
| `dataset_refs` | dataset IDs in this snapshot's `datasets[]` |
| `status` / `successor` | as Section 4 |

| edges | |
| --- | --- |
| `edge_id`, `from_node_id`, `to_node_id`, `relation_type` \* | relation ∈ prerequisite, enabler, alternative; `required: bool` — a prerequisite is treated as a required edge for cycle detection |

| datasets (D3.1 catalogue) | |
| --- | --- |
| `dataset_id`, `label` \* | `pf:wp3:dataset:<slug>` |
| seven characterisation attributes | `availability` (available/planned/limited/unknown), `suitability`, `quality`, `maturity`, `representativeness`, `completeness` (all 0–1), `ai_act_alignment` (aligned/conditional/gap/unassessed) — exactly the T3.1.1 list |

### 5.3 `pf.questionnaire.v1` — WP4 → WP2 (review) and to Pathfinder (runtime)

Source: WP4 objective ("receive input from WP2"), T4.1 self-evaluation tools. Producer owner: WP4. One snapshot **per stakeholder type** is normal (RFQ F01 requires ≥ 5 supported types); multiple active questionnaires coexist and the validator checks each against the taxonomy.

| field | rules |
| --- | --- |
| `stakeholder_type: ref` \* | MUST exist in the pinned taxonomy |
| `version`, `title`, `target_scenarios[]` \* | scenario IDs MUST exist, and each (stakeholder_type × scenario) pair MUST be supported: either `all` or the stakeholder appears in that scenario's `applicable_stakeholder_types` (RFQ §3.2 "supported stakeholder/scenario combinations" — enforced, not advisory) |
| `review_status` | draft → for-review → approved; WP2 approves by RFC sign-off on the snapshot |
| `questions[]` \* | `question_id: pf:wp4:question:<slug>`, `label`, `question_type` ∈ single_choice/multi_choice/numeric/text, `required: bool`; `options[]` for choice types; `min_value`/`max_value` for numeric |

Question annotations bind answers to state:

- `maturity_dimension`: taxonomy `dimension_id` (or null). When set on a numeric question, the scale **MUST be 1..5** (integer maturity, RFQ §3.2).
- `state_field`: capabilities \| missing_capabilities \| regulatory_flags — which StakeholderState list the answer feeds.
- `capability_maps_to`: maps answer options to `capability_vocabulary` tokens.
- `visible_if`: conditional visibility using the same boolean-tree grammar as rule conditions (Section 5.4).

### 5.4 `pf.rulebundle.v1` — WP8 → Pathfinder

Source: T8.2 (guideline, checklist, legal consequences), T8.3.1–3 (framework mapping, interplay, compliance paths), T4.1 ("road legal"). Producer owner: WP8. Depends on taxonomy + roadmap snapshots.

Payload: `references[]`, `rules[]`, `tests[]` (all required).

| references (regulatory registry) | |
| --- | --- |
| `ref_id: pf:wp8:reg:<slug>` \*, `instrument` \*, `status` \* | instrument ∈ EHDSR, GDPR, AI-Act, IVDR, MDR, HTAR, Data-Act, Biotech-Act, national, other; status ∈ in-force, provisional, forthcoming |
| `locator`, `eur_lex_uri` (format uri), `source_doc_ref` | where to find the text |

| rules | |
| --- | --- |
| `rule_id: pf:wp8:rule:<slug>` \*, `rule_type` \*, `priority: int` \*, `status` \* | rule_type ∈ eligibility, exclusion, preference, override; status ∈ verified, provisional |
| `applies_to` \* | stakeholder IDs or `all` — must exist in the pinned taxonomy |
| `condition` \* | recursive boolean tree: `{and: [...]}`, `{or: [...]}`, `{not: {...}}` or atomic `{field, op, value}` with op ∈ eq, ne, gt, gte, lt, lte, in, not_in, contains, exists. Fields are state paths over StakeholderState (dimension state_keys, capabilities, flags) |
| `action` \* | `{title, text}`; optional `node_id` (roadmap node advanced — must exist), `block: bool` (T8.2 legal-condition blocks), `warning` |
| `compliance_refs` \* | registry IDs **in this bundle**. A dangling ref is **not** rejected: it renders the rule's regulatory basis as `unverified` (see 6/7). Do not rely on this — resolve or add the reference |
| `parent_rule_id`, `effective_from`, `effective_until`, `rule_version`, `source_doc_ref` | rule tree + temporal validity (dates respected at evaluation time, Section 8) |

`provisional` status is the honest channel for forthcoming legislation (e.g. Biotech Act per T8.3.1): Pathfinder displays it as unverified and **never** as a legal conclusion.

| tests — executable, not decorative | |
| --- | --- |
| `test_id`, `rule_id` \*, `given` \*, `expect` \* | **Every rule MUST have at least one paired test**, and the validator **executes it**: `given` is a StakeholderState fixture whose fields must be declared state vocabulary; the expectation is checked against the real `ComplianceEvaluator` output. A test that disagrees with the engine fails the delivery (Gate 4) |

### 5.5 `pf.feedback.v1` — WP4 → WP2 / WP3 / WP8 (aggregate telemetry)

Source: T4.2 test drives, D4.3 (M27), T4.3 ("three-fold feedback … shared with the ancillary WPs 2, 3, 8"). Producer owner: WP4. Depends on all four upstream contracts.

| field | rules |
| --- | --- |
| `period: {from, to}` \*, `min_cohort_size: int ≥ 5` \*, `recipient` \* | recipient ∈ WP2, WP3, WP8 — **one snapshot per recipient**; the schema binds recipient to section and **forbids the other sections from being present** (WP8 never sees roadmap telemetry, WP2 never sees rule stats) |
| roadmap.node_stats (recipient WP3) | per node: `visits`, `as_current_position`, `as_target`, `blocked_by_prerequisite_count`, `label_incompleteness_reports`, `cohort_size` |
| roadmap.unsatisfiable_route_ids | nodes whose required routes could not be satisfied |
| rules.rule_stats (recipient WP8) | per rule: `evaluations`, `triggers`, `block_events`, `unverified_marker_count`, `cohort_size`; plus `never_fired_rule_ids` |
| questionnaire.question_stats (recipient WP2) | per question: `answers`, `abandonment_after`, `ambiguity_flags`, `cohort_size` |

Disclosure rules are enforced behaviourally (Gate 4), because aggregates are personal-data-adjacent:

- `cohort_size` < `min_cohort_size` → rejected;
- any count that is non-zero but below the cohort threshold → rejected (prevents re-identification by elimination);
- **rate fields are prohibited** — any numeric key ending in `rate` fails ("rates require a separate disclosure review"). Report counts; ratios can leak.

The threshold is a floor, **not** a substitute for a disclosure review of your own dataset.

## 6. Referential rules (Gate 3 in full)

| # | Rule | Scope |
| --- | --- | --- |
| R1 | Edge endpoints reference existing nodes | roadmap |
| R2 | Prerequisites reference existing nodes; **edges ∪ prerequisites** required-graph is acyclic | roadmap |
| R3 | `node.stakeholder_types` ∈ taxonomy IDs ∪ {all} | roadmap × taxonomy |
| R4 | `scenario.applicable_stakeholder_types` ∈ taxonomy IDs ∪ {all} | taxonomy |
| R5 | Questionnaire stakeholder × scenario combinations supported by taxonomy | questionnaire × taxonomy |
| R6 | Rule `applies_to` ∈ taxonomy IDs ∪ {all} | rulebundle × taxonomy |
| R7 | Rule `action.node_id` ∈ roadmap IDs | rulebundle × roadmap |
| R8 | `compliance_refs` resolve inside the bundle's `references`; unresolved → `unverified` warning, never rejection | rulebundle |
| R9 | `maturity_dimension` ∈ taxonomy `dimension_id`s | questionnaire × taxonomy |
| R10 | Every rule has ≥ 1 paired test; every test's `rule_id` exists | rulebundle |
| R11 | Numeric maturity questions use scale 1..5 | questionnaire |
| R12 | `maturity_level` ∈ 1..5 integers everywhere | all |
| R13 | `dependencies` closure resolves: named snapshots present, contract names agree, transitive | all |

When a check targets the "active" set (e.g. R3 against taxonomy), the validator uses the head(s) of each supersedes chain. Cross-set references to **superseded** snapshots fail — that is the point of R13.

## 7. Validation gates

| Gate | What it proves | Mechanism |
| --- | --- | --- |
| 1 · Schema | envelope shape, closed contract enum, producer binding, payload fields, enums, patterns | JSON Schema Draft 2020-12, offline (payload schemas inline-resolved) |
| 2 · Checksum | payload bytes match `items_checksum` under the Section 3.3 definition | recomputed, never trusted |
| 3 · Referential | R1–R13 above | `boundary_validation.referential_checks` |
| 4 · Behavioural | duplicate IDs within a snapshot; **paired rule tests executed** against the real evaluator; feedback cohort thresholds + count suppression + rate prohibition | `boundary_validation.behavioral_checks` |

Commands:

```sh
# validate the golden samples (what CI runs on every schema/sample change)
python3 scripts/validate_contracts.py

# validate a delivery: directory must contain the snapshot plus its full dependency closure
python3 scripts/validate_contracts.py --snapshot-dir path/to/delivery

# non-zero exit + exact field-path error messages; this exit code is your release gate
```

The validator never activates anything — it only judges. Activation is Pathfinder's (Section 8).

## 8. Delivery and activation flow

1. **Produce.** You emit `*.snapshot.json` into your release channel — git tag, artefact store, or the shared consortium folder `/snapshots/<contract>/`. Content-addressed storage recommended (checksum = filename is fine).
2. **Self-validate.** Your CI runs the delivery mode above on every emission. Our CI replays it. Identical code, so identical verdicts.
3. **Hand over.** The validating snapshot set is the handover. No secondary PDF/e-mail format is normative; the narrative Part B deliverable carries `derived_from` links, not replacements.
4. **Activate.** An administrator submits the complete generation to `POST /v1/admin/import` (`{"snapshots": [...]}`). Pathfinder builds and validates the generation, then — in PostgreSQL mode — commits snapshot identities, the immutable generation record, the active pointer and an audit event **in one transaction**. Legacy per-WP import endpoints are disabled in that mode.
5. **Pin.** Every assessment session created after activation pins the exact snapshot IDs **and the UTC evaluation date** it ran against. Later activations never mutate an existing session's questionnaire, roadmap or rules (RFQ F07/F08 reproducibility).
6. **Effective dates.** At evaluation time, rules outside `effective_from`/`effective_until` are excluded and the affected recommendation carries the `unverified` regulatory state. Provisional rules, unresolved `compliance_refs`, `forthcoming` instruments and missing references likewise render unverified; an otherwise-ready result is marked `degraded`, and a blocked result stays `blocked` while exposing unverified separately.

## 9. Runtime modes and production requirements

| Concern | `memory` (development) | `postgres` (production — required) |
| --- | --- | --- |
| Enable | `BOUNDARY_STORAGE=memory`, explicit | `ENVIRONMENT=production` **fails startup** unless `BOUNDARY_STORAGE=postgres` |
| Storage | process memory, lost on restart | immutable snapshot + generation tables; single active-pointer row |
| Activation | in-process swap | snapshot identities + generation + pointer + audit event in one transaction |
| Concurrency | — | sessions carry an optimistic `revision`; conflicting writes get a conflict response, never a silent overwrite |
| DB failure | — | **no fallback to memory**; database errors surface as a dedicated handler response |
| Tokens | may coincide | `PATHFINDER_DEMO_TOKEN` ≠ `PATHFINDER_ADMIN_TOKEN`, both required, else startup fails |
| Migration | n/a | idempotent, run **before** (re)starting workers: `DATABASE_URL=... python scripts/migrate_boundary_storage.py` |

Production data path: WP snapshot → validated generation → PostgreSQL (authoritative) → workers read the active pointer → assessments pinned per session. Mock upstream services are used only when no store is configured (development).

## 10. Versioning and change governance

- **Additive change** (new optional field, new enum member where absence-safe): bump `contract_version` minor. Old consumers still validate new snapshots; declare nothing else.
- **Breaking change** (renamed/removed field, changed semantics, tightened pattern): publish `pf.<name>.v2` — a new closed-enum entry via RFC, with `migration_notes` mandatory in the manifest of v2 snapshots and an **overlap window** during which both versions are accepted. Golden samples of v1 run against the v2 schema during the window as a CI job (the enum makes "unknown contract passes silently" impossible).
- **Content updates** (new roadmap node, corrected rule) are *not* version changes — they are new snapshots with `supersedes`. D3.2 (M36) is a roadmap content version, not a format change.
- **RFC procedure:** a markdown PR touching `contracts/` proposing schema diff + migration note + updated golden samples. Approval = sign-off of the producer owner **and** the consumer owner(s) (Section 11). Disagreement escalates to the WP4 lead at the next consortium call. The `contracts/` tree is the single source of truth; generated adapters/schemas elsewhere MUST be derived from it.
- **Freeze schedule:** draft at kick-off → schema baseline frozen at **M1** → content snapshots flowing from **M3** → after freeze, schema change only via RFC.

## 11. Obligations per work package

| WP | Must build | First delivery | Minimum interface surface |
| --- | --- | --- | --- |
| WP2 | taxonomy exporter + questionnaire review channel | D2.1 (M06) | IDs for the five stakeholder segments + roles + scenarios; capability vocabulary before questionnaire freeze; RFC sign-off on `review_status: for-review` snapshots |
| WP3 | roadmap exporter (D3.1 catalogue + nodes/edges) | D3.1 (M12), WP3/MS3.1 (M16) | stable node IDs, prerequisite/edge closure, seven dataset attributes; a ~300-line emitter is the expected effort ceiling |
| WP4 | questionnaire snapshots (≥ 5 stakeholder types) + feedback × 3 recipients per period | F01 set; feedback first at D4.3 window | combination support per RFQ §3.2; recipient-scoped, count-only feedback; cohort review |
| WP8 | rules-as-data bundle + paired executable tests | T8.2/T8.3.1 projection (v0 provisional OK) | every rule executable-tested; use `provisional` + forthcoming instruments honestly rather than forcing a false `verified` |

Every WP: add `python3 scripts/validate_contracts.py --snapshot-dir …` to your CI as a blocking step, and treat the validator's exit code as the only format arbitre.

## 12. Non-goals

- No ontology/Semantic-Web formats; JSON Schema only.
- No central data lake; the active generation lives inside Pathfinder's boundary store.
- No multilingual contracts in v1 (English slugs + labels; `metadata` is reserved so locale maps can arrive without contract change).
- No cross-language checksum claim beyond the three published vectors.
- No producer authentication in the envelope (channel-level control; signing is a v2 discussion).
- WP5/WP6/WP7 interactions (pilot scenarios, validation data, lessons learnt) are delivered through T4.2/T4.3 validation reporting, not through contracts; they become boundary contracts only by RFC if a machine consumer emerges in Pathfinder.

## 13. Grounding in Part B (traceability)

Each contract projects named Part B objects; `derived_from` binds entities to their source:

| Contract | Part B anchors |
| --- | --- |
| taxonomy | T2.1 (segments, role classification, needs, influence/interest), D2.1 (M06), MS4.1 axes |
| questionnaire | WP4 objective (input from WP2/WP3), T4.1 self-evaluation tools |
| roadmap | T3.1.1 (dataset attributes), T3.3 (action categories, horizons, responsibilities), D3.1 (M12), WP3/MS3.1 (M16), D3.2 (M36) |
| rule bundle | T4.1 ("road legal"), T8.2 (guideline + checklist + legal consequences), T8.3.1 (framework mapping incl. forthcoming Biotech Act), T8.3.2 (interplay EHDSR × AI-Act × IVDR/MDR × HTAR), T8.3.3 (compliance paths) |
| feedback | T4.2 (test drives), T4.3 (three-fold feedback to WP2/WP3/WP8), D4.3 (M27) |

## 14. File inventory

```text
contracts/
  envelope.schema.json              manifest + closed contract enum + producer bindings
  ids.md                            ID rules (Section 4, normative copy)
  checksum-vectors.json             Gate-2 conformance vectors
  wp2-taxonomy.schema.json          pf.taxonomy.v1
  wp3-roadmap.schema.json           pf.roadmap.v1
  wp4-questionnaire.schema.json     pf.questionnaire.v1
  wp8-rulebundle.schema.json        pf.rulebundle.v1
  wp4-feedback.schema.json          pf.feedback.v1 (recipient-scoped)
  samples/*.snapshot.json           7 golden samples = fixtures + documentation + CI input
pathfinder/core/boundary_validation.py   the four gates (single implementation)
pathfinder/core/boundary_runtime.py      generation assembly from validated snapshots
pathfinder/adapters/boundary.py          boundary → runtime question mapping
pathfinder/core/repositories/boundary_store.py  PostgreSQL store, generations, revisions
scripts/validate_contracts.py        thin CLI shim over the gates
scripts/migrate_boundary_storage.py  idempotent production migration
docs/15_wp_boundary_contracts.md     design rationale (why each rule exists)
docs/reviews/16_…                    xiaolong review + P0 fix log (lineage)
```

## 15. FAQ (the five questions we expect)

**Q: We keep our roadmap in Notion/Excel. Compliant?** A: Yes — export to `pf.roadmap.v1` via a small emitter. Only the snapshot is binding.

**Q: A node's meaning changed but the ID must stay for our internal links.** A: Impossible under rule 4.3: semantic change at a constant ID = breaking change = `migration_notes` + RFC. Allocate a new ID and deprecate the old with `successor`.

**Q: Can we send the file by e-mail and import it manually?** A: The e-mail can carry it; validity is the validator's exit code. Manual import exists (`POST /v1/admin/import`) but your CI must already be green.

**Q: Our legal text lands after M12.** A: Expected. Emit v0 with `provisional` status and `forthcoming` instruments; Pathfinder renders unverified honestly. Update via `supersedes` when in force.

**Q: Why can't our feedback include "abandonment rate"?** A: Rates over small cohorts are re-identification vectors. Publish the two counts and let each recipient compute ratios under its own review.

## 16. Complete JSON samples

The HTML edition embeds the full JSON files from `contracts/samples/`, including each snapshot's `contract`, `manifest` and `payload`. These are the same golden samples used by the validator; they are illustrative fixtures, not approved partner deliveries or verified legal guidance.

Expand a sample to read its JSON, or copy or download the complete file. All sample contents are embedded in the HTML, so viewing, copying and downloading work offline. The source JSON files remain authoritative; running `python3 scripts/build_protocol_html.py` refreshes the embedded copies.

### 16.1 Source files

- [WP2 stakeholder taxonomy](../contracts/samples/wp2-taxonomy.snapshot.json)
- [WP3 roadmap](../contracts/samples/wp3-roadmap.snapshot.json)
- [WP4 questionnaire](../contracts/samples/wp4-questionnaire.snapshot.json)
- [WP8 regulatory rule bundle](../contracts/samples/wp8-rulebundle.snapshot.json)
- [WP4 feedback to WP2](../contracts/samples/wp4-feedback-wp2.snapshot.json)
- [WP4 feedback to WP3](../contracts/samples/wp4-feedback.snapshot.json)
- [WP4 feedback to WP8](../contracts/samples/wp4-feedback-wp8.snapshot.json)

### 16.2 Embedded JSON

<!-- CONTRACT_SAMPLES -->

---

*End of protocol. Deviations, errata and extensions: RFC against `contracts/`, per Section 10.*
