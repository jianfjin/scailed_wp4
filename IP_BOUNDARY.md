# Pathfinder V1 IP Boundary

Status: Draft for contract review.

## Background IP
- `pathfinder/core/graph.py`: generic in-memory graph traversal pattern.
- `pathfinder/core/solver.py`: generic deterministic path solving pattern.
- `pathfinder/core/compliance.py`: generic rule condition evaluator.

## SCAILED Foreground IP
- `pathfinder/adapters/demo_data.py`: SCAILED-specific demo stakeholder, roadmap, and rule examples.
- `pathfinder/services/assessment_service.py`: SCAILED Pathfinder V1 orchestration.
- `pathfinder/api/`: SCAILED Pathfinder V1 API surface.
- `frontend/`: SCAILED Pathfinder V1 React demo shell.

## WP-Provided Content
- Future WP2 stakeholder taxonomy data.
- Future WP3 roadmap data.
- Future WP8 regulatory rule bundles and test cases.

## Third-Party Dependencies
- FastAPI and Uvicorn for API serving.
- React and Vite for frontend build.
- PyYAML for optional YAML rule parsing.

GPL/AGPL dependencies require written approval before use.
