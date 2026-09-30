# SCAILED WP4 / EPIDATA Pathfinder Proposal

This directory is the Markdown source of truth for the seven-volume EPIDATA Pathfinder proposal package. It turns the repository's V1 product baseline into a coherent technical and procurement-ready document set.

## Scope baseline

The proposal describes Pathfinder V1 as an auditable EHDS readiness path planner. A stakeholder selects a profile and scenario, completes a structured assessment, receives a deterministic roadmap path, and exports traceable evidence for review.

V1 deliberately excludes production multi-tenancy, patient data, automated legal decisions, direct HDAB/SPE/AI Factory integrations, an AI copilot, GraphRAG recommendations, and production Kubernetes/Terraform/Helm operations. Those subjects appear only as integration context or future evolution.

## Volumes

| Volume | Document | Purpose |
| --- | --- | --- |
| 01 | [Executive & Business Requirements](volume-01-executive-business-requirements.md) | Case for action, outcomes, stakeholders, scope, and success criteria |
| 02 | [Software Requirements Specification](volume-02-software-requirements-specification.md) | Functional, quality, security, and traceability requirements |
| 03 | [System Architecture & Technical Design](volume-03-system-architecture.md) | Components, data flow, deployment, auditability, and design decisions |
| 04 | [Request for Proposal](volume-04-request-for-proposal.md) | Supplier instructions, work packages, deliverables, and evaluation |
| 05 | [API & Data Specification](volume-05-api-data-specification.md) | Contracts, versioning, schemas, and OpenAPI surface |
| 06 | [Demo Dataset Specification](volume-06-demo-dataset-specification.md) | Safe, reproducible demo fixtures and validation rules |
| 07 | [Project Plan & Deliverables](volume-07-project-plan.md) | Work breakdown, milestones, acceptance evidence, and governance |

Supporting artifacts:

- [Architecture diagrams](diagrams/architecture.md)
- [JSON Schemas](schemas/)
- [OpenAPI contract](openapi/pathfinder-v1.yaml)

## Source and status

Prepared from the repository baseline on 2026-09-30. The primary local sources are `docs/12_merged_pathfinder_spec.md`, `docs/pathfinder-workflow.md`, `docs/03_partners.md`, `docs/02_project_dependencies.md`, `docs/05_pathfinder_diagrams.md`, `docs/graph-architecture/how-the-graph-is-built.md`, and the WP2/WP3/WP8 mock fixtures.

This package is a proposal and technical baseline, not a legal opinion. Regulatory references and partner-provided rules require review and versioning by the responsible WP8 contributors.

## Doc-as-code workflow

Markdown files are authoritative. Render PDFs into `pdf/` with a pinned document toolchain, for example:

```bash
./scripts/build_proposal_pdfs.sh
```

The helper uses `pandoc` when available and otherwise falls back to Python-Markdown plus LibreOffice. It writes one PDF per volume.

Generated PDFs are release artifacts; do not edit them directly.
