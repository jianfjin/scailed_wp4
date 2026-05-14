# SCAILED WP4 Pathfinder System — 扩展分析

## 第一部分：合同条款建议

### 一、付款结构

基于张雪峰的审计，建议三级付款：

| 里程碑 | 比例 | 触发条件 | 绑定上游 |
|--------|------|----------|----------|
| 预付款 | 30% | 合同签署后15日内 | 无 |
| Phase 1 完成 | 30% | M9: 核心引擎 + mock数据全链路通过 | Epidata收到CHARITE M9付款 |
| D4.1 交付 | 40% | M20: D4.1验收通过 | Epidata收到CHARITE M20付款 |

关键：**第二、三期付款绑定Epidata从CHARITE收到对应节点款项**，不是绑定DataWego自身交付。防止Epidata现金流断裂时DataWego垫背。

### 二、范围边界（必须写入合同）

**包含（DataWego交付）：**
- Pathfinder System V1 软件（T4.1 scope）
- 源代码 + Docker Compose部署包
- API文档（OpenAPI spec自动生成）
- 用户操作手册（README级别）
- D4.1 Demo录屏支持
- D4.2 Stakeholder Event 技术支持

**明确排除（另签合同）：**
- Pathfinder V2 开发（T4.3, CHARITE牵头）
- D4.3/D4.4 报告撰写（CHARITE责任）
- WP5/6/7 集成开发（各WP自身责任）
- 生产环境运维
- 多语言支持
- 用户培训

### 三、验收标准（量化）

| 项目 | 标准 |
|------|------|
| 支持利益相关者类型 | ≥5种 (基于WP2分类) |
| 推荐路径生成 | 每种类型 ≥3条可执行路径 |
| 合规检查准确率 | WP8已知规则100%匹配 |
| 前端响应时间 | ≤3秒（标准问卷提交） |
| 代码覆盖率 | ≥80% (pytest) |
| 部署文档 | CHARITE人员可在一小时内完成部署 |

### 四、返工条款

因以下原因导致的返工，按 €X/人天 计费，不在固定价格内：
1. WP2/WP3/WP8 上游数据格式变更
2. Epidata 需求变更（超出签字原型范围）
3. EHDS 实施细则中途颁布导致逻辑变更

### 五、知识产权

- DataWego 保留核心引擎代码著作权
- Epidata 获得 SCAILED 项目范围内的永久使用许可
- Pathfinder System 在SCAILED项目外的商业化需另议

---

## 第二部分：技术实现细节

### 一、数据 Schema 设计

#### 问卷定义 (questionnaires)

```sql
CREATE TABLE questionnaires (
    id              SERIAL PRIMARY KEY,
    version         TEXT NOT NULL,           -- 'v1.0-m3-freeze'
    stakeholder_type TEXT,                   -- from WP2
    definition      JSONB NOT NULL,          -- 问题树结构
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

`definition` JSONB 结构：
```json
{
  "title": "EHDS Readiness Self-Assessment",
  "sections": [
    {
      "id": "s1",
      "title": "Organizational Profile",
      "questions": [
        {
          "id": "q1.1",
          "text": "What is your primary role in the biotech value chain?",
          "type": "single_choice",
          "options": [
            {"id": "drug_discovery", "label": "Drug Discovery"},
            {"id": "clinical_trials", "label": "Clinical Trials"},
            {"id": "diagnostics", "label": "Diagnostics/IVD"},
            {"id": "digital_health", "label": "Digital Health/AI"}
          ],
          "maps_to_dimension": "stakeholder_category",
          "weight": 1.0
        }
      ]
    }
  ]
}
```

#### 路线图节点 (roadmap_nodes)

```sql
CREATE TABLE roadmap_nodes (
    id              SERIAL PRIMARY KEY,
    node_id         TEXT UNIQUE NOT NULL,    -- 'R2.3-A'
    label           TEXT NOT NULL,           -- 'Establish DPO'
    description     TEXT,
    parent_node     TEXT,                    -- self-ref for DAG
    prerequisites   TEXT[],                  -- ['R1.2', 'R2.1']
    dimension       TEXT,                    -- 'governance'|'technical'|'legal'
    maturity_level  INT CHECK (maturity_level BETWEEN 1 AND 5),
    effort_estimate TEXT,                    -- 'low'|'medium'|'high'
    related_wp      TEXT,                    -- 'WP5'|'WP6'|'WP7'
    x               FLOAT,
    y               FLOAT,                  -- visualization
    metadata        JSONB,
    schema_version  TEXT NOT NULL            -- 'v1.0-m3-freeze'
);
```

#### 推荐规则 (recommendation_rules)

```sql
CREATE TABLE recommendation_rules (
    id                SERIAL PRIMARY KEY,
    rule_id           TEXT UNIQUE NOT NULL,   -- 'R-PHARMA-AI-001'
    node_id           TEXT REFERENCES roadmap_nodes(node_id),
    stakeholder_type  TEXT,
    
    -- 条件：JSONB 支持复杂查询
    -- {"answers": {"q2.1": {"gte": 3}, "q3.2": ["A","B"]}}
    condition         JSONB NOT NULL,
    
    -- 推荐动作
    action_title      TEXT NOT NULL,
    action_text       TEXT NOT NULL,          -- "Establish a Data Protection Officer role"
    
    -- 合规引用（数组，方便批量更新）
    compliance_ref    TEXT[],                 -- ['GDPR-Art.37', 'EHDS-Art.50']
    
    -- 优先级
    priority          INT DEFAULT 0,
    
    -- 来源追溯
    source_wp         TEXT,                   -- 'WP3'|'WP8'
    source_doc_ref    TEXT,                   -- 上游文档引用
    
    -- 版本
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now(),
    rule_version      TEXT NOT NULL
);

CREATE INDEX idx_rules_stakeholder ON recommendation_rules(stakeholder_type);
CREATE INDEX idx_rules_node ON recommendation_rules(node_id);
CREATE INDEX idx_rules_condition ON recommendation_rules USING GIN (condition);
```

#### 评估会话 + 审计日志

```sql
CREATE TABLE assessment_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stakeholder_type TEXT,
    status          TEXT DEFAULT 'in_progress', -- 'in_progress'|'completed'|'abandoned'
    answers         JSONB,                     -- 完整答案快照
    current_node    TEXT REFERENCES roadmap_nodes(node_id),
    recommendations JSONB,                     -- 生成的推荐快照
    created_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

-- 审计日志（不可篡改）
CREATE TABLE audit_log (
    id              SERIAL PRIMARY KEY,
    session_id      UUID REFERENCES assessment_sessions(id),
    event_type      TEXT NOT NULL,            -- 'answer_submitted'|'recommendation_generated'|'report_exported'
    event_data      JSONB NOT NULL,
    timestamp       TIMESTAMPTZ DEFAULT now(),
    ip_hash         TEXT,                     -- 匿名化
    user_agent_hash TEXT
);

-- 审计日志只追加，不更新不删除
CREATE RULE audit_no_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE RULE audit_no_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING;
```

### 二、Python 核心引擎结构

```
pathfinder/
├── core/
│   ├── __init__.py
│   ├── models.py          # Pydantic models
│   ├── graph.py           # DAG operations (NetworkX)
│   ├── solver.py          # Dijkstra shortest path
│   ├── compliance.py      # Constraint checker
│   └── recommend.py       # Recommendation engine
├── api/
│   ├── __init__.py
│   ├── main.py            # FastAPI app
│   ├── routes/
│   │   ├── assessments.py # /v1/assessments/*
│   │   ├── roadmap.py     # /v1/roadmap/*
│   │   └── compliance.py  # /v1/compliance/*
│   └── dependencies.py    # DI
├── adapters/
│   ├── wp2_stakeholders.py
│   ├── wp3_roadmap.py
│   └── wp8_compliance.py
├── rules/
│   ├── pharma_rules.yaml
│   ├── sme_rules.yaml
│   └── academia_rules.yaml
├── frontend/
├── tests/
│   ├── test_graph.py
│   ├── test_solver.py
│   ├── test_compliance.py
│   └── test_recommend.py
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

### 三、核心算法（简化实现）

```python
# pathfinder/core/solver.py
import networkx as nx
from typing import List, Optional
from .models import StakeholderState, RoadmapNode, Recommendation, PathResult

class PathfinderSolver:
    """Core pathfinding on regulatory DAG."""
    
    def __init__(self, graph: nx.DiGraph):
        # 启动时验证 DAG
        if not nx.is_directed_acyclic_graph(graph):
            raise ValueError("EWD498: Roadmap graph must be a DAG")
        self.graph = graph
    
    def locate(self, state: StakeholderState) -> RoadmapNode:
        """Find current position on roadmap."""
        best_node = None
        best_score = float('inf')
        
        for node_id in self.graph.nodes:
            node = self.graph.nodes[node_id]
            if not self._is_compliant(state, node):
                continue
            score = self._distance(state, node)
            if score < best_score:
                best_score = score
                best_node = node
        
        if best_node is None:
            raise NoFeasiblePositionError("No compliant position found")
        return best_node
    
    def plan_path(self, current: RoadmapNode, target: RoadmapNode, 
                  state: StakeholderState) -> PathResult:
        """Dijkstra shortest path under compliance constraints."""
        # 只考虑合规节点
        valid_nodes = {n for n in self.graph.nodes 
                       if self._is_compliant(state, self.graph.nodes[n])}
        subgraph = self.graph.subgraph(valid_nodes)
        
        path = nx.shortest_path(subgraph, current.node_id, target.node_id, 
                                weight='cost')
        cost = nx.shortest_path_length(subgraph, current.node_id, 
                                        target.node_id, weight='cost')
        
        # 生成可执行建议
        recommendations = self._path_to_recommendations(path, state)
        return PathResult(path=path, cost=cost, 
                          recommendations=recommendations)
    
    def _is_compliant(self, state: StakeholderState, node: dict) -> bool:
        """Check all WP8 constraints for (state, node) pair."""
        for constraint in node.get('compliance_constraints', []):
            if not constraint.evaluate(state):
                return False
        return True
```

---

## 第三部分：认证与数据安全

### 需要 DataWego 做吗？

**张雪峰/Jensen 的判断：不需要完整的认证系统。**

理由：
1. Pathfinder V1 是 Demo（D4.1 类型 = 报告+演示），不是生产系统
2. 用户是受邀利益相关者（Stakeholder Forum 内部）
3. T4.2 Test Drive 阶段 CHARITE 负责部署，安全是他们的事
4. 如果加认证 → 需要用户管理、密码重置、OAuth集成 → 范围爆炸

### DataWego 应该做的安全措施

**1. 最小认证（Phase 2 加入）**
- 简单 Token-based 访问控制
- 生成一批一次性访问链接，发给 Stakeholder Event 参与者
- 不需要注册/登录/密码

```python
# 简单实现
SECRET_TOKENS = set(os.environ.get("ACCESS_TOKENS", "").split(","))

@app.middleware("http")
async def simple_token_auth(request, call_next):
    if request.url.path.startswith("/v1/assessments"):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token not in SECRET_TOKENS:
            return JSONResponse(status_code=403, content={"error": "unauthorized"})
    return await call_next(request)
```

**2. 数据最小化**
- 不存储个人身份信息（PII）
- 评估会话用 UUID，不关联邮箱/姓名
- `audit_log` 中 `ip_hash` 和 `user_agent_hash`（单向哈希）

**3. 传输安全**
- HTTPS（Nginx反向代理 + Let's Encrypt）
- API 响应不含敏感的内部错误信息

**4. 数据留存**
- 评估数据保留到项目结束（M36）
- D4.1 交付后的数据由 CHARITE 负责

### 不需要 DataWego 做的安全

- ❌ GDPR 合规声明 — WP8 负责
- ❌ 数据保护影响评估 (DPIA) — CHARITE/Epidata 负责
- ❌ EHDS 数据访问权限 — SCAILED 数据治理框架负责
- ❌ SPE 环境安全 — AI Factory/WP7 负责
- ❌ 用户认证SDK — 范围外

### Guido 的审计追踪（必须做）

每个评估会话的每次答案修改、每次推荐生成 → 不可篡改日志：
```sql
-- 审计日志表特点：
-- 1. 只追加（RULE禁止UPDATE/DELETE）
-- 2. 每个事件带 timestamp
-- 3. 包含回答快照（JSONB）
-- 4. 包含推荐快照（可追溯"Why this recommendation?")
-- 5. IP/UA 哈希化（匿名但可验证）
```

---

## 第四部分：与上游对接清单

### M1-M3 必须完成

| 对接对象 | 需要什么 | 格式 | 签字人 |
|----------|----------|------|--------|
| WP3 (CHARITE) | 战略路线图节点-边列表 | JSON + 拓扑排序证明 | WP3 Lead |
| WP8 (Lead TBD) | 法规约束可执行规则 | YAML 规则文件 | WP8 Lead |
| WP2 (IISLAFE) | 利益相关者分类矩阵 | JSON Schema | WP2 Lead |
| SHAIPED | 现有代码/数据审计 | Code audit report | Lu Zhao |

### M4-M18 持续对接

| 对接对象 | 需要什么 | 提供什么 |
|----------|----------|----------|
| WP5 (ELIXIR) | 数据基础设施规格 | Pathfinder API endpoint（验证用） |
| WP6 (Lead TBD) | 用例定义+评估标准 | Pathfinder 实例 + 测试数据集 |
| WP7 (AI Factories) | SPE 环境参数 | Docker 镜像 + 部署文档 |

---

*扩展分析完。与九龙决议合并，形成完整项目方案。*
*路径: ~/projects/scailed_wp4/council_debate_20260513/*
