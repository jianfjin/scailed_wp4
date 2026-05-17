# D4.1 Technical Appendix

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
python -m unittest discover -s tests -v
python -m compileall pathfinder api
python -m pathfinder.demo
npm install
npm run build
openspec validate add-merged-pathfinder-v1 --strict
```

## Open Implementation Items
- PostgreSQL AGE persistence is still represented by deployment SQL and not wired into runtime code.
- API rate limiting is not yet implemented in-process.
- Docker Compose boot has not yet been verified in this pass.
- Frontend is React by decision.
