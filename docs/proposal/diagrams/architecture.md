# Pathfinder V1 Architecture Diagrams

These diagrams are the proposal-level views. They intentionally show the V1 deterministic core; future AI/GraphRAG and production infrastructure are outside the acceptance baseline.

## Context and containers

```mermaid
flowchart LR
  WP2[WP2 stakeholder taxonomy] --> Import[Validated snapshot imports]
  WP3[WP3 roadmap nodes and edges] --> Import
  WP8[WP8 rules and test cases] --> Import
  Import --> Store[(Versioned active snapshots)]
  User[Invited demo participant] --> API[FastAPI V1]
  API --> Service[Assessment service]
  Service --> Store
  Service --> Q[Questionnaire engine]
  Service --> R[Rule evaluator]
  Service --> G[Roadmap graph and solver]
  Service --> Audit[Append-only audit chain]
  Service --> Report[Traceable report]
```

## Assessment sequence

```mermaid
sequenceDiagram
  participant U as Participant
  participant A as API
  participant S as Assessment service
  participant Q as Questionnaire
  participant R as Rules
  participant G as Roadmap graph
  participant T as Audit/report
  U->>A: create session(profile, scenario)
  A->>S: create and bind active versions
  S->>Q: load questionnaire
  U->>A: submit answers
  A->>S: derive stakeholder state
  S->>R: evaluate deterministic rules
  S->>G: locate nodes and search path
  G-->>S: path, blockers, warnings
  S->>T: append event and build traceable report
  A-->>U: status, path, evidence, disclaimer
```

## Data lineage

```mermaid
flowchart TB
  Raw[Partner or generated source] --> Validate[Schema + referential validation]
  Validate -->|valid| Snapshot[Immutable snapshot + checksum]
  Validate -->|invalid| Reject[Reject activation + diagnostic]
  Snapshot --> Activate[Active version]
  Activate --> Session[Session binding]
  Session --> Result[Recommendation and report]
  Result --> Evidence[Trace: answers, nodes, rules, refs, versions]
```
