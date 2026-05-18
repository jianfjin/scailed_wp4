# D4.1 Technical Appendix

## Acceptance Gate (Council Governance, 2026-05-18)

The CI smoke test (`deploy/smoke_test.py`) is the **sole acceptance gate** for Pathfinder V1. If it fails, the PR does not merge. No human override.

Local `P4 green` does not override CI smoke-test red. This eliminates the dual-responsibility gap identified in the 2026-05-18 council post-mortem.

## Architecture
Pathfinder V1 is implemented as a modular monolith:

- React frontend in `frontend/`
- FastAPI wrapper in `pathfinder/api/`
- deterministic core engine in `pathfinder/core/`
- demo data adapters in `pathfinder/adapters/`
- orchestration service in `pathfinder/services/`

## Demo Mode
Until WP2, WP3, and WP8 provide structured data, Pathfinder runs with demo fixtures:

- five stakeholder types
- versioned questionnaires
- roadmap nodes and prerequisite edges
- deterministic WP8-style rule bundle
- paired rule tests
- mock-data warning in UI/report output

## Verification

**Primary acceptance gate**: `make gate` (or `bash deploy/smoke-test.sh`) — the CI smoke test is the sole merge gate. If it fails, no merge.

Supporting verification:
```bash
make gate        # smoke + verify + unit tests (merge gate)
make test        # python3 -m pytest tests/ -v
python3 scripts/verify_tasks.py --strict   # tasks.md → test coverage
python3 -m pathfinder.demo                 # CLI demo output
cd frontend && npm install && npm run build  # frontend build
openspec validate add-merged-pathfinder-v1 --strict
```

## Open Implementation Items
- PostgreSQL AGE is wired as the runtime graph backend with an in-memory V1 solver projection; full table-backed hydration of questionnaires, rules, sessions, and audit data remains future persistence work.
- API rate limiting is implemented in-process for V1 demo protection; deployed edge rate limiting remains a deployment hardening option.
- Docker Compose configuration validates, but a full container boot has not yet been verified in this pass.
- Frontend is React by decision.
