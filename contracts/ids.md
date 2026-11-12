# ID namespace rules (normative)

Format: `pf:<wp>:<type>:<slug>` — slug is lowercase `[a-z0-9-]{1,64}`, unique per `<wp>:<type>`.

| Type slot | Owner | Example |
| --- | --- | --- |
| `stakeholder` | WP2 | `pf:wp2:stakeholder:biotech-sme` |
| `scenario` | WP2 | `pf:wp2:scenario:secondary-use-readiness` |
| `dimension` | WP2 | `pf:wp2:dimension:maturity-data` |
| `persona` | WP2 | `pf:wp2:persona:sme-regulatory-lead` |
| `node` | WP3 | `pf:wp3:node:governance-framework-v1` |
| `edge` | WP3 | `pf:wp3:edge:gov-v1-enables-catalog` |
| `dataset` | WP3 | `pf:wp3:dataset:priority-oncology-registry` |
| `rule` | WP8 | `pf:wp8:rule:ehdsr-art9-eligibility` |
| `reg` | WP8 | `pf:wp8:reg:eur-lex-2016-679` |
| `question` | WP4 | `pf:wp4:question:biotech-sme-data-catalog-q3` |

Stability rules (from `docs/15_wp_boundary_contracts.md` §4):

1. An ID is assigned once and never reused, even after deprecation.
2. Deprecated entities stay visible with `status: "deprecated"` plus `successor` for at least one major contract version.
3. Labels/descriptions/metadata may change at a constant ID; identity never changes. Semantic change at the same ID = breaking change + migration note.
4. Split = new IDs + tombstone old; merge = retire one, keep one, record alias in `metadata.id_aliases`.

Entity-level string fields named `*_type`, `applicable_*`, `applies_to` either carry such an ID or the wildcard `"all"`. (`prerequisites`, `compliance_refs`, `dataset_refs` are ID-only — a wildcard there is meaningless.)

Part B milestone references in `derived_from` must carry their WP qualifier (`WP3/MS3.1`), because Part B milestone numbering collides across work packages (WP1/MS3.1 "Project Completed" vs WP3/MS3.1 "Initial Strategic Roadmap").
