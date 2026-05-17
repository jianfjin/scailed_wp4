# Change: Add Merged Pathfinder V1

## Why
SCAILED WP4 needs a bounded Pathfinder V1/demo for D4.1 that can turn stakeholder self-assessment answers into auditable EHDS readiness next steps. The current repository has product, design, and execution source documents, but no OpenSpec change record that preserves the agreed V1 scope, non-goals, quality gates, and delivery plan.

## What Changes
- Add the `merged-pathfinder` capability as an auditable EHDS readiness path planner.
- Define guided assessments, stakeholder state modeling, roadmap positioning, deterministic path planning, rule evaluation, traceability, reporting, controlled imports, graceful degradation, and audit logging.
- Preserve V1 scope boundaries: demo-grade Pathfinder, deterministic rules, mock-data fallback, Docker Compose deployment, and no production SaaS, AI copilot, GraphRAG, real EHDS integrations, or full account management.
- Capture the modular monolith technical direction from `docs/13_merged_pathfinder_design.md`.
- Capture implementation phases from `docs/14_merged_pathfinder_plan.md`.

## Impact
- Affected specs: `merged-pathfinder`
- Affected docs: `docs/12_merged_pathfinder_spec.md`, `docs/13_merged_pathfinder_design.md`, `docs/14_merged_pathfinder_plan.md`
- Affected code: future `pathfinder/`, `deploy/`, and test suites
- Delivery gate: proposal approval required before implementation
