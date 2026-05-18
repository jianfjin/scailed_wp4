# Mock Upstream REST Services — 实现方案

**Branch**: feature/mock-upstream-rest-services
**Date**: 2026-05-18
**决策**: 陛下否决议会6:1投票，坚持mock REST方向

## 架构

```
                    ┌─────────────┐
                    │  Pathfinder │  aiohttp.ClientSession
                    │  Backend    │────────────┐
                    └─────────────┘            │
                           │                  │
              ┌────────────┼──────────┐       │
              ▼            ▼          ▼       │
        ┌─────────┐ ┌─────────┐ ┌─────────┐   │
        │wp2-mock │ │wp3-mock │ │wp8-mock │◄──┘
        │:8102    │ │:8103    │ │:8108    │  GET /api/v1/*
        │aiohttp  │ │aiohttp  │ │aiohttp  │
        └─────────┘ └─────────┘ └─────────┘
```

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
  wp2-mock:
    build: services/mock/Dockerfile.mocks
    command: python wp2_stakeholders.py
    ports: ["8102:8080"]
    networks: [backend]
    healthcheck: curl -f http://localhost:8080/health

  wp3-mock:
    build: services/mock/Dockerfile.mocks
    command: python wp3_roadmap.py
    ports: ["8103:8080"]
    networks: [backend]

  wp8-mock:
    build: services/mock/Dockerfile.mocks
    command: python wp8_rules.py
    ports: ["8108:8080"]
    networks: [backend]
```

### 3. Pathfinder Adapter 改造

```python
# pathfinder/adapters/upstream.py (新文件)
import aiohttp
from pathfinder.core.models import StakeholderState, RoadmapNode, RoadmapEdge, Rule

class UpstreamClient:
    def __init__(self, wp2_url, wp3_url, wp8_url):
        self.wp2_url = wp2_url
        self.wp3_url = wp3_url
        self.wp8_url = wp8_url
        self._session = None
    
    async def fetch_stakeholders(self) -> list[dict]:
        """GET wp2-mock/api/v1/stakeholders → stakeholder taxonomy"""
        ...
    
    async def fetch_roadmap(self) -> tuple[list[RoadmapNode], list[RoadmapEdge]]:
        """GET wp3-mock → nodes + edges → domain models"""
        ...
    
    async def fetch_rules(self) -> list[Rule]:
        """GET wp8-mock → rules → domain models"""
        ...
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
