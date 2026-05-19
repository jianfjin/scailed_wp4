# SCAILED WP4 — Startup Verification: Mock Fixture Data Flow

> **Document version:** 2026-05-19  
> **Branch:** feature/mock-upstream-rest-services  
> **Context:** Live verification — the running containers are confirmed to use mock fixture data (wp3_data.json) via automatic FastAPI lifespan startup. No manual data loading was performed.

---

## TL;DR

The graph in the running containers was built **automatically** by FastAPI at startup — not manually. The data came from the WP3 mock service (serving `wp3_data.json`), not from hardcoded `demo_data.py`. Confirmed via live API query.

---

## 1. What Actually Happened

```
Human action:  docker compose up -d --build
               (one command, no data loading)

System action:  FastAPI lifespan startup (automatic)
                 ├── UpstreamClient.startup()
                 │     GET wp2-mock:8080  → stakeholder taxonomy
                 │     GET wp3-mock:8080  → roadmap nodes + edges  ← wp3_data.json
                 │     GET wp8-mock:8080  → rules
                 │
                 ├── AssessmentService(upstream_client=client)
                 │     → _load_upstream_data()  (NOT _load_demo_data)
                 │
                 └── connect_age()
                       → load_demo_data(nodes, edges)
                           ├── load_projection()  → self.nodes / self.edges
                           └── AGE MERGE          → pathfinder_graph
```

---

## 2. Live Verification

### Health Endpoint

```
GET /health
Authorization: Bearer demo-token
```

```json
{
    "status": "ok",
    "service": "pathfinder",
    "mode": "deployed",
    "graph_backend": "age",
    "stakeholder_types": [
        "ai-factory-operator",
        "biotech-sme",
        "health-data-access-body",
        "health-data-infrastructure",
        "research-infrastructure"
    ],
    "rule_version": null,
    "audit_events": 0,
    "audit_chain_valid": true,
    "import_reports": {
        "upstream": {
            "source": "upstream",
            "accepted": true,
            "checksum": "df538e6ad4189736cdba750ba7565ea16c77034858888d0c7f44a50e4625c10f",
            "snapshot_version": "upstream-df538e6ad418",
            "warnings": [],
            "activated_records": 20
        }
    }
}
```

**Key evidence:**
- `"mode": "deployed"` — not demo
- `"graph_backend": "age"` — not inmemory
- `"import_reports": {"upstream": {...}}` — has "upstream", NOT "demo"
- No warning: "demo mode: partner WP2/WP3/WP8 inputs not loaded"

If the system had fallen back to `demo_data.py`, the response would show:
```json
"import_reports": {
    "demo": {
        "warnings": ["demo mode: partner WP2/WP3/WP8 inputs not loaded"]
    }
}
```

### Roadmap Endpoint

```
GET /v1/roadmap
Authorization: Bearer demo-token
```

Returns exactly 6 nodes + 6 edges matching `services/mock/fixtures/wp3_data.json`:

| node_id | label | dimension | maturity |
|---|---|---|---|
| generic-intake | Confirm stakeholder baseline | governance | 1 |
| governance-scope | Define governance scope | governance | 2 |
| legal-basis | Confirm legal basis | compliance | 3 |
| secure-processing | Prepare secure processing environment | data | 4 |
| access-body-review | Prepare HDAB review package | compliance | 4 |
| readiness-report | Export readiness evidence | governance | 5 |

Edges: e1–e6, all `relation_type: prerequisite`.

---

## 3. The Decision Point

In `AssessmentService.__init__()` (`assessment_service.py` line 66-69):

```python
# ── Data source: upstream client (mock REST) or demo fixtures ──
if upstream_client is not None:
    self._load_upstream_data(upstream_client)   # ← THIS PATH (deployed)
else:
    self._load_demo_data()                      # ← Fallback (dev/test only)
```

FastAPI lifespan (`main.py` line 72-76):
```python
_service = AssessmentService(
    use_age=None,
    startup_check=False,
    upstream_client=_upstream_client,  # ← NOT None → triggers upstream path
)
```

Since `upstream_client` is always provided in the FastAPI lifespan, the deployed path is taken. The demo path is only reached when `AssessmentService()` is created with no arguments (tests, CLI).

---

## 4. Container Topology at Verification Time

```
scailed-traefik    Up 31h    :80→80
scailed-frontend   Up 4h     80/tcp (healthy)
scailed-backend    Up 4h     8000/tcp (healthy)
scailed-postgres   Up 4h     5432/tcp (healthy)
scailed-redis      Up 31h    6379/tcp
scailed-wp2-mock   Up 4h     8102→8080 (healthy)
scailed-wp3-mock   Up 4h     8103→8080 (healthy)
scailed-wp8-mock   Up 4h     8108→8080 (healthy)
```

### Verification Commands

```bash
# Check mode and data source
curl -s http://localhost:80/health -H "Authorization: Bearer demo-token" | python3 -m json.tool

# Check graph contents
curl -s http://localhost:80/v1/roadmap -H "Authorization: Bearer demo-token" | python3 -m json.tool

# Check individual node
curl -s http://localhost:80/v1/roadmap/legal-basis -H "Authorization: Bearer demo-token" | python3 -m json.tool
```

---

## 5. Two Data Sources, One Interface

The system transparently supports both — the graph backend doesn't care:

| | Demo | Upstream (Active) |
|---|---|---|
| **Trigger** | `upstream_client is None` | `upstream_client is not None` |
| **Data from** | `demo_data.demo_roadmap()` | WP3 mock → `wp3_data.json` |
| **Import report key** | `"demo"` | `"upstream"` |
| **Warning message** | "partner WP inputs not loaded" | (none) |
| **Graph content** | 6 nodes, 6 edges | 6 nodes, 6 edges |
| **Content identical?** | Yes (same data, two expressions) | Yes |

Both paths produce identical `list[RoadmapNode] + list[RoadmapEdge]`. The same 6-node DAG. The difference is only in provenance tracking.

---

## 6. How to Switch

To force demo mode (bypass mock services):
```bash
# In docker-compose.yml, change:
PATHFINDER_MODE=demo
# Or remove WP3_API_URL to cause upstream fetch failure → fallback
```

To switch to real WP3 consortium API:
```bash
# In docker-compose.yml, change:
WP3_API_URL=https://real-wp3.consortium.eu/api/v1
# Same UpstreamClient, different URL — zero code change
```

---

## 7. Key Insight

No one "built the graph manually." The system is self-initializing:

1. Docker Compose starts all 8 containers
2. WP3 mock boots, loads `wp3_data.json` into memory
3. Backend boots, FastAPI lifespan fires
4. `UpstreamClient` HTTP-fetches from WP3 mock (with retry)
5. `AssessmentService` constructs domain models from JSON
6. `connect_age()` dual-writes to memory + PostgreSQL/AGE
7. System is ready — all automatic, zero manual steps

The `/health` endpoint is the single source of truth for verifying which path was taken.
