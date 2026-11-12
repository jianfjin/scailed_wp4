# contracts/ — WP boundary interface contracts

Normative, machine-readable contracts for data crossing the WP2 / WP3 / WP4 / WP8
boundaries of SCAILED Pathfinder V1. Companion document: `docs/15_wp_boundary_contracts.md`.

Layout:

```text
contracts/
  envelope.schema.json         common snapshot manifest + payload binding (all contracts)
  ids.md                       ID namespace and stability rules (normative)
  wp2-taxonomy.schema.json     pf.taxonomy.v1       B1  WP2 -> WP4
  wp4-questionnaire.schema.json pf.questionnaire.v1 B2  WP4 -> WP2 (review channel)
  wp3-roadmap.schema.json      pf.roadmap.v1        B3  WP3 -> WP4 (+ D3.1 dataset catalog)
  wp8-rulebundle.schema.json   pf.rulebundle.v1     B4  WP8 -> WP4 (+ references + paired tests)
  wp4-feedback.schema.json     pf.feedback.v1       B5-B7  WP4 -> WP3/WP8/WP2 (aggregated)
  samples/*.snapshot.json      golden samples: test fixture, validator input, documentation
```

Verify everything (schema + canonical checksum + referential integrity):

```text
python3 scripts/validate_contracts.py
```

To validate a delivery, pass `--snapshot-dir PATH`; include the exact dependencies
referenced in each manifest. The validator also executes the rule examples and
checks feedback suppression. This command does not activate data in Pathfinder.

Rules of the game:

- A snapshot is `{contract, manifest, payload}`; the manifest is identical across contracts.
- `manifest.derived_from` names the Part B deliverable(s) (D2.1, D3.1, D3.2/MS3.1, T8.2/T8.3.x) the payload projects.
- IDs (`pf:<wp>:<type>:<slug>`) are forever; labels change freely, identity does not (ids.md).
- Schema evolution: additive = minor; breaking = new `vN` + migration notes + overlap window.
- Each WP's internals are free; only this format is binding.
- Feedback is scoped to one recipient; the cohort threshold and count suppression
  are not a substitute for a disclosure review.
- `POST /v1/admin/import` accepts a complete runtime snapshot set. Production
  uses transactional PostgreSQL activation, durable version bindings and a
  shared audit chain. Apply `scripts/migrate_boundary_storage.py` before startup;
  see `docs/15_wp_boundary_contracts.md` for role grants and configuration.
