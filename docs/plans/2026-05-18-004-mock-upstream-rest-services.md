# Mock Upstream REST Services — 实现方案

**Branch**: feature/mock-upstream-rest-services  
**Date**: 2026-05-18  
**决策**: 陛下否决议会6:1投票，坚持mock REST方向

## 相关文档

- **架构图**: [docs/diagrams/2026-05-18-architecture-8-containers.html](../diagrams/2026-05-18-architecture-8-containers.html)
- **技术规格**: [docs/specs/2026-05-18-mock-upstream-rest-services.html](../specs/2026-05-18-mock-upstream-rest-services.html)

## 完整 Docker Compose 拓扑 (8容器)

```
                     ┌──────────────────────────────────────────────────┐
                     │        Docker Compose — scailed_wp4              │
                     │                                                  │
  User ──HTTPS──→ ┌──────────┐                                         │
                  │ traefik  │  :80 (reverse proxy, TLS, rate-limit)    │
                  │ v3.7     │                                         │
                  └────┬─────┘                                         │
                       │                                               │
          ┌────────────┼────────────┐                                  │
          ▼            ▼            │                                  │
    ┌──────────┐ ┌──────────┐       │                                  │
    │ frontend │ │ backend  │       │                                  │
    │ nginx    │ │ FastAPI  │       │                                  │
    │ React    │ │ :8000    │       │                                  │
    │ :80(int) │ │ aiohttp  │       │                                  │
    └──────────┘ └──┬──┬──┬─┘       │                                  │
                    │  │  │         │                                  │
         ┌──────────┘  │  └──────────────────┐                         │
         ▼              ▼                     │                         │
    ┌─────────┐   ┌─────────┐                 │                         │
    │postgres │   │ redis 7 │    ┌────────────┼────────────┐           │
    │PG16+AGE │   │ :6379   │    │     Mock Services       │           │
    │:5432    │   │ cache   │    │  ┌──────────────────┐   │           │
    │named vol│   │named vol│    │  │ wp2-mock  :8102  │◄──┤           │
    └─────────┘   └─────────┘    │  │ aiohttp.web      │   │           │
                                 │  │ Stakeholders     │   │           │
                                 │  ├──────────────────┤   │           │
                                 │  │ wp3-mock  :8103  │◄──┤           │
                                 │  │ aiohttp.web      │   │           │
                                 │  │ Roadmap Nodes    │   │           │
                                 │  ├──────────────────┤   │           │
                                 │  │ wp8-mock  :8108  │◄──┘           │
                                 │  │ aiohttp.web      │               │
                                 │  │ Rules + Tests    │               │
                                 │  └──────────────────┘               │
                                 └────────────────────────────────────┘
                     └──────────────────────────────────────────────────┘
```

## 数据流

```
1. User → Traefik :80                  HTTPS (浏览器 / CLI)
2. Traefik → Frontend                  Static React SPA (PathPrefix `/`)
3. Traefik → Backend                   API calls (PathPrefix `/api`, `/v1`, `/health`)
4. Backend → PostgreSQL                SQL + AGE Cypher (graph node CRUD)
5. Backend → Redis                     Session cache / rule hot-reload lock
6. Backend → wp2-mock :8102           aiohttp GET /api/v1/stakeholders
7. Backend → wp3-mock :8103           aiohttp GET /api/v1/roadmap/nodes + /edges
8. Backend → wp8-mock :8108           aiohttp GET /api/v1/rules
```

## 网络隔离

```
frontend network: traefik + frontend + backend (代理层, 仅端口80流量)
backend network:  backend + postgres + redis + wp*-mock (业务层, 无公网暴露)
```

PostgreSQL, Redis, Mock Services 均仅加入 `backend` 网络 — 外部零可达。

## aiohttp 双角色

一个库覆盖两端：
- **服务端**: `aiohttp.web` — 3个微服务，每个<80行
- **客户端**: `aiohttp.ClientSession` — Pathfinder adapter用async fetch替代demo_data.py

## 实现清单

### 1. Mock Services (每个<80行)

```
services/mock/
├── Dockerfile.mocks           # 统一Dockerfile (python:3.12-slim + aiohttp)
├── wp2_stakeholders.py        # WP2 mock: GET /api/v1/stakeholders, GET /api/v1/stakeholders/{type}
├── wp3_roadmap.py             # WP3 mock: GET /api/v1/roadmap/nodes, GET /api/v1/roadmap/edges
├── wp8_rules.py               # WP8 mock: GET /api/v1/rules, GET /api/v1/rules/{id}
└── fixtures/
    ├── wp2_data.json          # 10 stakeholders with capabilities/pain_points
    ├── wp3_data.json          # 20 roadmap nodes + 15 edges
    └── wp8_data.json          # 15 rules + paired tests
```

API contract:
```
WP2: GET /api/v1/stakeholders → [{stakeholder_type, description, capabilities, pain_points}]
WP3: GET /api/v1/roadmap/nodes → [{node_id, label, dimension, maturity_level, prerequisites}]
     GET /api/v1/roadmap/edges → [{from_node_id, to_node_id, relation_type}]
WP8: GET /api/v1/rules → [{rule_id, rule_type, priority, condition, action, compliance_refs}]
```

### 2. Docker Compose (+3 services)

```yaml
  # ─── WP2 Mock — Stakeholder Taxonomy ───
  wp2-mock:
    build:
      context: services/mock
      dockerfile: Dockerfile.mocks
    image: scailed/wp2-mock:latest
    container_name: scailed-wp2-mock
    restart: unless-stopped
    command: python wp2_stakeholders.py
    ports:
      - "8102:8080"
    networks:
      - backend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 15s
      timeout: 3s
      retries: 3

  # ─── WP3 Mock — Roadmap Graph ───
  wp3-mock:
    build:
      context: services/mock
      dockerfile: Dockerfile.mocks
    image: scailed/wp3-mock:latest
    container_name: scailed-wp3-mock
    restart: unless-stopped
    command: python wp3_roadmap.py
    ports:
      - "8103:8080"
    networks:
      - backend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 15s
      timeout: 3s
      retries: 3

  # ─── WP8 Mock — Rules Engine ───
  wp8-mock:
    build:
      context: services/mock
      dockerfile: Dockerfile.mocks
    image: scailed/wp8-mock:latest
    container_name: scailed-wp8-mock
    restart: unless-stopped
    command: python wp8_rules.py
    ports:
      - "8108:8080"
    networks:
      - backend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 15s
      timeout: 3s
      retries: 3
```

### 3. Pathfinder Adapter 改造

```python
# pathfinder/adapters/upstream.py (新文件)
import aiohttp
import os
from typing import Optional
from pathfinder.core.models import StakeholderState, RoadmapNode, RoadmapEdge, Rule

class UpstreamClient:
    """Async client for upstream WP services (mock or real).
    
    Environment variables:
      WP2_API_URL  → http://wp2-mock:8080/api/v1 (demo)
      WP3_API_URL  → http://wp3-mock:8080/api/v1 (demo)
      WP8_API_URL  → http://wp8-mock:8080/api/v1 (demo)
    """
    
    def __init__(self, wp2_url=None, wp3_url=None, wp8_url=None):
        self.wp2_url = wp2_url or os.getenv("WP2_API_URL", "")
        self.wp3_url = wp3_url or os.getenv("WP3_API_URL", "")
        self.wp8_url = wp8_url or os.getenv("WP8_API_URL", "")
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _ensure_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
    
    async def fetch_stakeholders(self) -> list[dict]:
        """GET wp2-mock/api/v1/stakeholders → stakeholder taxonomy"""
        await self._ensure_session()
        async with self._session.get(f"{self.wp2_url}/stakeholders") as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def fetch_roadmap(self) -> tuple[list[dict], list[dict]]:
        """GET wp3-mock → nodes + edges → domain models"""
        await self._ensure_session()
        async with self._session.get(f"{self.wp3_url}/roadmap/nodes") as resp:
            nodes = await resp.json()
        async with self._session.get(f"{self.wp3_url}/roadmap/edges") as resp:
            edges = await resp.json()
        return nodes, edges
    
    async def fetch_rules(self) -> list[dict]:
        """GET wp8-mock → rules → domain models"""
        await self._ensure_session()
        async with self._session.get(f"{self.wp8_url}/rules") as resp:
            resp.raise_for_status()
            return await resp.json()
    
    async def close(self):
        if self._session:
            await self._session.close()
```

### 4. AssessmentService 集成

```python
class AssessmentService:
    def __init__(self, use_age=False, upstream_client=None):
        if upstream_client:
            self.upstream = upstream_client
            # 启动时fetch一次，缓存到self.graph / self.rules
        else:
            # fallback: demo_data.py (开发/测试)
            ...
```

## 工作量

| 任务 | 文件 | 估时 |
|------|------|------|
| wp2 mock | services/mock/wp2_stakeholders.py (~50行) | 0.5d |
| wp3 mock | services/mock/wp3_roadmap.py (~60行) | 0.5d |
| wp8 mock | services/mock/wp8_rules.py (~60行) | 0.5d |
| Dockerfile + compose | Dockerfile.mocks + compose edits | 0.5d |
| fixtures JSON | 3 JSON文件 (从demo_data.py导出) | 0.5d |
| UpstreamClient adapter | pathfinder/adapters/upstream.py (~120行) | 1d |
| AssessmentService改造 | 集成upstream_client | 0.5d |
| aiohttp→requirements | requirements.txt | 0.1d |
| 测试 | test_upstream.py | 0.5d |
| **总计** | | **4.5人天** |

## 切换真实API

```bash
# Demo (mock containers)
export WP2_API_URL=http://wp2-mock:8080/api/v1
export WP3_API_URL=http://wp3-mock:8080/api/v1
export WP8_API_URL=http://wp8-mock:8080/api/v1

# Production (real WP services)
export WP2_API_URL=https://scailed-consortium.eu/wp2/api/v1
export WP3_API_URL=https://scailed-consortium.eu/wp3/api/v1
export WP8_API_URL=https://scailed-consortium.eu/wp8/api/v1
```

UpstreamClient代码不动，只改环境变量。

## 风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Mock fixtures diverge from real APIs | High | Medium | JSON Schema contracts agreed with WP leads by M3 |
| aiohttp dep conflicts with FastAPI | Low | Low | FastAPI uses Starlette, no known conflicts |
| Mock network unavailable on startup | Medium | Critical | depends_on + healthcheck; backend retries 3x |
| 8 containers exceed single-VM resources | Low | Medium | Mock containers ~50MB each; 3 mocks ≈ 150MB |
