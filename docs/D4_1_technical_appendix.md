# D4.1 Technical Appendix

## Acceptance Gate (Council Governance, 2026-05-18)

The smoke test (`make smoke-test`, wrapping `deploy/smoke_test.py`) is the **sole Pathfinder V1 acceptance gate**. If it fails, the PR does not merge. No human override.

Local unit/API tests do not override smoke-test red. This eliminates the dual-responsibility gap identified in the 2026-05-18 council post-mortem.

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
Current verification commands:

```powershell
make test
make verify-tasks
make smoke-test
make ci
```

Supporting commands behind those targets:

```powershell
python -m pytest tests -q
python -m compileall pathfinder api scripts
python -m pathfinder.demo
npm install
npm run build --prefix frontend
openspec validate add-merged-pathfinder-v1 --strict
```

`make smoke-test` requires a deployed Docker Compose stack and checks the functional data path, including AGE graph backend status. `scripts/verify_tasks.py --strict` is a consistency checker for checked OpenSpec tasks; it does not replace the smoke-test acceptance gate. P95 latency checks are informational and intentionally not a hard gate.

## Open Implementation Items
- PostgreSQL AGE is wired as the runtime graph backend with an in-memory V1 solver projection; full table-backed hydration of questionnaires, rules, sessions, and audit data remains future persistence work.
- API rate limiting is implemented in-process for V1 demo protection; deployed edge rate limiting remains a deployment hardening option.
- Docker Compose configuration validates, but a full container boot must be verified through `make smoke-test`.
- Frontend is React by decision.
