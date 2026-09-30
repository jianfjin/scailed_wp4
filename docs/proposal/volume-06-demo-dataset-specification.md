# Volume 06 — Demo Dataset Specification

## 1. Purpose and safety boundary

The demo dataset proves the Pathfinder flow without requiring patient data or production partner systems. It is synthetic, deterministic, versioned, and clearly labeled as non-authoritative. It must not contain names, contact details, dates of birth, health records, patient IDs, or re-identification keys.

## 2. Dataset packages

| Package | Contents | Source role |
| --- | --- | --- |
| WP2 | Stakeholder types, descriptions, capabilities, pain points | Questionnaire/profile inputs |
| WP3 | Roadmap nodes, dimensions, maturity, prerequisites, applicability | Graph/path inputs |
| WP8 | Rules, conditions, actions, regulatory references, rule tests | Compliance/path constraints |
| Session cases | Curated answer sets and expected outcomes | Repeatable acceptance scenarios |

The repository's current mock fixtures use generated WP2/WP3/WP8 records and a `secondary-use-readiness` scenario. Generated rules carry a warning and must be distinguished from an official WP8 bundle.

## 3. Required demo coverage

The release fixture shall contain at least:

- five stakeholder types, including biotech SME, AI Factory operator, health data access body, health data infrastructure, and research infrastructure;
- one complete questionnaire template applicable to every supported demo type;
- three cases with an `ok` path;
- one case with a blocking rule;
- one case with an incomplete-data `degraded` result;
- roadmap nodes across governance, data, and compliance dimensions;
- rules covering eligibility, exclusion, preference, and override behavior;
- paired expected outcomes for every curated rule.

## 4. Example curated cases

| Case | Profile | Expected result | Evidence |
| --- | --- | --- | --- |
| DEMO-01 | biotech-sme | `ok` | data catalog and legal-basis capabilities satisfy initial path. |
| DEMO-02 | health-data-access-body | `ok` or `degraded` | governance and regulatory evidence present; warnings visible if labels are incomplete. |
| DEMO-03 | research-infrastructure | `blocked` | missing audit-log or other eligibility prerequisite triggers a blocker. |
| DEMO-04 | AI Factory operator | `degraded` | missing upstream rule or roadmap value produces explicit unverified warning. |

## 5. Generation and reproducibility

Dataset generation shall use a pinned seed and write snapshot metadata containing schema version, generator version, creation date, record counts, and checksum. A fixture reload must yield identical IDs and equivalent recommendation outputs. Any generated value must be recognizable as generated and must not resemble a real person or organization in a way that creates confusion.

## 6. Quality checks

1. Validate each JSON file against its schema.
2. Check uniqueness of IDs and referential integrity of edges/rules.
3. Check that every rule test references a rule and expected result.
4. Check that no forbidden identifier fields occur.
5. Check that all accepted stakeholder types have a questionnaire path.
6. Run the curated cases and compare normalized results.
7. Record checksums in the import report.

## 7. Data lifecycle

Demo snapshots are disposable and may be regenerated. They are not a source of truth for legal or operational policy. When partner data becomes available, import it as a new immutable snapshot, compare counts and semantics, run the rule/roadmap acceptance suite, and retain the demo snapshot for regression testing.

## 8. Regulatory and clinical coding note

The demo does not require patient-level clinical coding. If future use cases add clinical concepts, preserve original source codes and provenance, use an appropriate canonical terminology strategy, and do not treat ICD-10, SNOMED CT, LOINC, and ATC as interchangeable mappings. This is a future integration concern, not a V1 demo dependency.
