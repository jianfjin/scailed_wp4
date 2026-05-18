---
type: "query"
date: "2026-05-18T05:53:29.832491+00:00"
question: "What connects audit_chain_valid, assessment_id, schema_version to rest of system?"
contributor: "graphify"
source_nodes: ["audit_chain_valid", "assessment_id", "schema_version"]
---

# Q: What connects audit_chain_valid, assessment_id, schema_version to rest of system?

## Answer

The graph shows these fields as weakly connected leaf nodes. audit_chain_valid, assessment_id, and schema_version each connect by EXTRACTED contains edges to e2e_output/m3_e2e_demo_d50f5aa.json and/or e2e_output/m3_e2e_docker_d50f5aa.json. The semantic E2E output nodes connect onward to D4.1 demo documentation, but the structural JSON field nodes are not bridged to those semantic output nodes. schema_version also appears in contract schema nodes as version/type leaves, but there is no extracted edge tying E2E schema_version to those contracts. Main graph gap: add semantic edges from E2E JSON outputs to D4.1 docs, AssessmentService, AuditLog, and schema contracts.

## Source Nodes

- audit_chain_valid
- assessment_id
- schema_version