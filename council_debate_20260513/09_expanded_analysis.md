# SCAILED WP4 Pathfinder System — 扩展分析

## 第一部分：合同条款建议

### 一、付款结构

基于张雪峰的审计，建议四级付款：

| 里程碑 | 比例 | 触发条件 | 绑定上游 |
|--------|------|----------|----------|
| 预付款 | 30% | 合同签署后15日内 | 无 |
| Phase 1 完成 | 15% | M9: 核心引擎 + mock数据全链路通过 | Epidata收到CHARITE M9付款 |
| Phase 1 完成（递延） | 15% | M15: 中期稳定版本验收通过 | Epidata收到CHARITE M15付款 |
| D4.1 交付 | 40% | M20: D4.1验收通过 | Epidata收到CHARITE M20付款 |

**关键保护条款：**

- **上游绑定**：第二至四期付款绑定Epidata从CHARITE收到对应节点款项，不是绑定DataWego自身交付。防止Epidata现金流断裂时DataWego垫背。
- **递延垫付条款**：若 CHARITE 延迟付款超过30天，Epidata 须先行垫付该期款项给 DataWego，再自行向 CHARITE 追偿。此条款防止上游付款链条的单点阻塞导致 DataWego 现金流中断。

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
| 代码覆盖率 | shell模块 ≥80%, kernel模块 ≥98% (pytest) |
| 部署文档 | CHARITE人员可在一小时内完成部署 |

### 四、返工条款

因以下原因导致的返工，按以下三级费率计费，不在固定价格内：

| 级别 | 日费率 | 适用场景 |
|------|--------|----------|
| Architect | €800–1,200/天 | 系统架构变更、跨模块重构 |
| Senior | €600–800/天 | 核心模块开发、算法调整 |
| Junior | €400–600/天 | 文档更新、测试补充、简单适配 |

**返工流程：**
1. Epidata 向 DataWego 提交书面返工请求（描述变更范围 + 理由）
2. DataWego 在 5 工作日内提供工作量估算和级别分配
3. 双方书面确认后方可启动
4. 超出估算 20% 以上的部分需重新确认

**返工触发条件（固定价格范围外）：**
1. WP2/WP3/WP8 上游数据格式变更
2. Epidata 需求变更（超出签字原型范围）
3. EHDS 实施细则中途颁布导致逻辑变更

**返工上限：**
- 单次返工 ≤ 合同总价的 15%
- 年度累计返工 ≤ 合同总价的 30%
- 超出上限的部分需重新谈判或另签合同

### 五、知识产权

采用 Background/Foreground IP 分拆模型：

**Background IP（各方保留）：**
- DataWego 保留入场前已有的通用组件、工具库、框架代码
- Epidata 保留其业务方法论和咨询框架
- 逐文件所有权清单详见 [IP_BOUNDARY.md](IP_BOUNDARY.md)

**Foreground IP（项目产出）：**
- Pathfinder System V1 核心引擎代码：DataWego 保留著作权
- Epidata 获得 SCAILED 项目范围内的永久、不可撤销、免版税使用许可
- 联合开发部分（如 WP3 集成适配层、上游数据连接器）：双方共有，任一方可在非竞争场景下使用
- Pathfinder System 在 SCAILED 项目外的商业化需另签协议，DataWego 享有优先谈判权

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
    schema_version  TEXT NOT NULL,           -- 'v1.0-m3-freeze'
    schema_version_id INT REFERENCES schema_versions(id)
);
```

#### 推荐规则 (recommendation_rules)

```sql
CREATE TYPE rule_type AS ENUM (
    'eligibility',    -- 资格判断：该利益相关者是否有资格获得此推荐
    'exclusion',      -- 排除规则：特定条件下排除此推荐
    'preference',     -- 偏好排序：同类推荐中的优先级偏好
    'override'        -- 覆盖规则：特殊情况下覆盖默认推荐逻辑
);

CREATE TABLE recommendation_rules (
    id                SERIAL PRIMARY KEY,
    rule_id           TEXT UNIQUE NOT NULL,   -- 'R-PHARMA-AI-001'
    parent_rule_id    TEXT,                   -- 父规则引用（规则组合/继承）
    rule_type         rule_type NOT NULL DEFAULT 'eligibility',
    node_id           TEXT REFERENCES roadmap_nodes(node_id),

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
CREATE INDEX idx_rules_parent ON recommendation_rules(parent_rule_id);
CREATE INDEX idx_rules_type ON recommendation_rules(rule_type);
CREATE INDEX idx_rules_priority ON recommendation_rules(priority DESC);
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

-- 审计日志（不可篡改，密码学链式完整性）
CREATE TABLE audit_log (
    id              SERIAL PRIMARY KEY,
    session_id      UUID REFERENCES assessment_sessions(id),
    event_type      TEXT NOT NULL,            -- 'answer_submitted'|'recommendation_generated'|'report_exported'
    event_data      JSONB NOT NULL,
    timestamp       TIMESTAMPTZ DEFAULT now(),
    ip_hash         TEXT,                     -- 匿名化单向哈希
    client_ip_hash  TEXT,                     -- 客户端IP哈希
    user_agent_hash TEXT,
    prev_hash       TEXT                      -- 上一条记录的 SHA-256，形成密码学链
);

-- 审计日志只追加，不更新不删除（使用 TRIGGER 替代 RULE，性能更优且兼容性更好）
CREATE OR REPLACE FUNCTION audit_log_prevent_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: UPDATE and DELETE are forbidden';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_no_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_prevent_mutation();

CREATE TRIGGER audit_no_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_prevent_mutation();
```

#### 新增表：版本管理 & 上游快照

```sql
-- Schema 版本追踪
CREATE TABLE schema_versions (
    id              SERIAL PRIMARY KEY,
    version         TEXT UNIQUE NOT NULL,     -- 'v1.0-m3-freeze'
    applied_at      TIMESTAMPTZ DEFAULT now(),
    description     TEXT,
    migration_file  TEXT,                     -- 'migrations/003_add_prev_hash.sql'
    checksum        TEXT                      -- SQL文件 SHA-256
);

-- 规则版本追踪（独立于 schema 版本，规则可能跨 schema 版本不变）
CREATE TABLE rule_versions (
    id              SERIAL PRIMARY KEY,
    rule_id         TEXT NOT NULL,
    rule_version    TEXT NOT NULL,
    change_type     TEXT,                     -- 'create'|'update'|'deprecate'
    change_summary  TEXT,
    schema_version_id INT REFERENCES schema_versions(id),
    applied_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(rule_id, rule_version)
);

-- 上游数据快照（可追溯 "M3 freeze 时上游数据长什么样"）
CREATE TABLE upstream_data_snapshots (
    id              SERIAL PRIMARY KEY,
    source_wp       TEXT NOT NULL,            -- 'WP2'|'WP3'|'WP8'
    source_doc_ref  TEXT,
    snapshot_data   JSONB NOT NULL,           -- 上游数据完整快照
    schema_version_id INT REFERENCES schema_versions(id),
    frozen_at       TIMESTAMPTZ DEFAULT now(),
    reason          TEXT                      -- 'M3 freeze'|'WP8 update v2.1'
);
```

### 二、Python 核心引擎结构

```
pathfinder/
├── core/
│   ├── __init__.py
│   ├── models.py          # Pydantic models
│   ├── graph.py           # DAG operations (Apache AGE primary, NetworkX fallback)
│   ├── solver.py          # Dijkstra shortest path
│   ├── compliance.py      # Constraint checker
│   └── recommend.py       # Recommendation engine
├── api/
│   ├── __init__.py
│   ├── main.py            # FastAPI app
│   ├── routes/
│   │   ├── assessments.py # /v1/assessments/*
│   │   ├── roadmap.py     # /v1/roadmap/*
│   │   ├── compliance.py  # /v1/compliance/*
│   │   └── admin.py       # /admin/rules/reload
│   ├── middleware/
│   │   ├── rate_limit.py  # Token bucket rate limiter
│   │   └── audit.py       # 自动审计日志记录
│   └── dependencies.py    # DI
├── adapters/
│   ├── wp2_stakeholders.py
│   ├── wp3_roadmap.py
│   └── wp8_compliance.py
├── services/
│   ├── graph_service.py       # ThreadPoolExecutor-wrapped graph operations
│   └── extraction_service.py  # WP3 Plan B: 数据提取层
├── config/
│   ├── settings.py
│   └── rate_limit.yaml
├── rules/
│   ├── pharma_rules.yaml
│   ├── sme_rules.yaml
│   └── academia_rules.yaml
├── migrations/
│   ├── 001_initial_schema.sql
│   ├── 002_add_recommendation_rules.sql
│   └── 003_add_prev_hash.sql
├── exceptions/
│   ├── __init__.py
│   └── handlers.py
├── scripts/
│   ├── seed_data.py
│   └── validate_rules.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── sample_graph.json
│   │   ├── sample_questionnaire.json
│   │   └── sample_rules.yaml
│   ├── test_graph.py
│   ├── test_solver.py
│   ├── test_compliance.py
│   ├── test_recommend.py
│   ├── test_rules.py          # .test.yaml rule test framework
│   └── benchmark/
│       └── test_graph_perf.py # pytest-benchmark
├── frontend/                   # 移出 Python package，独立前端项目
│   ├── src/
│   ├── public/
│   └── package.json
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── README.md
```

### 三、核心算法（简化实现）

```python
# pathfinder/core/solver.py
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from .models import StakeholderState, RoadmapNode, Recommendation, PathResult
from .graph import GraphEngine  # Abstracts Apache AGE / NetworkX

# ThreadPoolExecutor for graph operations (CPU-bound DAG traversal)
_graph_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="graph-")

class PathfinderSolver:
    """Core pathfinding on regulatory DAG.

    Graph Engine Strategy:
      - Primary: Apache AGE (PostgreSQL native graph extension)
        Rationale: NetworkX (pure Python) crashes with >200 nodes due to
        in-memory DAG operations exhausting Python heap on large regulatory
        graphs. Apache AGE runs graph algorithms inside PostgreSQL, leveraging
        its memory management and persistence. Benchmarks show 10-50x
        improvement on graphs with 200+ nodes.
      - Fallback: NetworkX for local dev/testing (no PostgreSQL dependency).
        Auto-selected when AGE connection is unavailable.
    """

    def __init__(self, graph_engine: GraphEngine):
        # 启动时验证 DAG
        if not graph_engine.is_directed_acyclic():
            raise ValueError("EWD498: Roadmap graph must be a DAG")
        self.graph = graph_engine

    def locate(self, state: StakeholderState) -> RoadmapNode:
        """Find current position on roadmap."""
        best_node = None
        best_score = float('inf')

        nodes = self.graph.get_all_nodes()
        for node in nodes:
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
        """Dijkstra shortest path under compliance constraints.
        Graph operations run via ThreadPoolExecutor to avoid blocking the
        async event loop.
        """
        # Run CPU-bound graph traversal in thread pool
        future = _graph_executor.submit(
            self._plan_path_sync, current, target, state
        )
        return future.result()

    def _plan_path_sync(self, current: RoadmapNode, target: RoadmapNode,
                        state: StakeholderState) -> PathResult:
        """Synchronous path computation (runs in ThreadPoolExecutor)."""
        valid_nodes = {n.id for n in self.graph.get_all_nodes()
                       if self._is_compliant(state, n)}

        path = self.graph.shortest_path(
            current.node_id, target.node_id,
            valid_nodes=valid_nodes, weight='cost'
        )
        cost = self.graph.shortest_path_length(
            current.node_id, target.node_id,
            valid_nodes=valid_nodes, weight='cost'
        )

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

### 四、API 端点设计

```
# 核心评估端点
POST   /v1/assessments                              # 创建评估会话
GET    /v1/assessments/{session_id}                  # 获取会话状态
POST   /v1/assessments/{session_id}/answers          # 提交答案
GET    /v1/assessments/{session_id}/recommendations  # 获取推荐
GET    /v1/assessments/{session_id}/report           # 导出报告

# 路线图端点
GET    /v1/roadmap                                   # 获取完整路线图
GET    /v1/roadmap/nodes/{node_id}                   # 获取节点详情

# 合规端点
GET    /v1/compliance/check                          # 合规检查
GET    /v1/compliance/rules                          # 列出所有规则

# 问卷模板端点（新增）
GET    /v1/questionnaires/{type}                     # 按利益相关者类型获取问卷模板

# 健康检查 & 管理端点（新增）
GET    /health                                        # 健康检查（liveness/readiness）
POST   /admin/rules/reload                            # 热加载规则文件（无需重启）

# 限流策略
# - /v1/assessments/* : 60 req/min per IP (token bucket)
# - /v1/roadmap/*     : 120 req/min per IP
# - /health            : unlimited
# - /admin/*           : 10 req/min per IP + Bearer token auth
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
- `audit_log` 中 `ip_hash`、`client_ip_hash` 和 `user_agent_hash`（单向哈希）

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
-- 1. 只追加（BEFORE UPDATE/DELETE TRIGGER 阻止修改，比 RULE 更可靠）
-- 2. 每个事件带 timestamp
-- 3. 包含回答快照（JSONB）
-- 4. 包含推荐快照（可追溯 "Why this recommendation?"）
-- 5. IP/UA 哈希化（匿名但可验证）
-- 6. prev_hash 字段形成密码学链：每条记录哈希包含上一条记录的哈希
--    → 任何中间记录的篡改都会导致后续所有记录的哈希不匹配
--    → 满足 EHDS 审计追踪的不可否认性要求
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

## 第五部分：测试策略（补充）

### 覆盖率分模块要求

| 模块 | 最低覆盖率 | 工具 | 说明 |
|------|-----------|------|------|
| shell (API, adapters, routes) | ≥80% | pytest + pytest-cov | 集成测试为主 |
| kernel (core: graph, solver, compliance, recommend) | ≥98% | pytest + pytest-cov + pytest-benchmark | 单元测试全覆盖，关键算法性能基准 |

### 规则测试框架 (.test.yaml)

每个规则文件附带一个 `.test.yaml` 文件，定义该规则的测试用例：

```yaml
# rules/pharma_rules.test.yaml
rule_file: pharma_rules.yaml
scenarios:
  - name: "pharma_ai_company_must_establish_dpo"
    stakeholder_type: "drug_discovery"
    answers:
      q1.1: "drug_discovery"
      q2.1: 4
      q3.2: ["A"]
    expected_recommendations:
      - rule_id: "R-PHARMA-AI-001"
        action: "present"
    expected_exclusions:
      - rule_id: "R-SME-EXEMPT-003"
        action: "absent"

  - name: "small_pharma_below_threshold_no_dpo_required"
    stakeholder_type: "drug_discovery"
    answers:
      q1.1: "drug_discovery"
      q2.1: 1
      q4.1: "<10_employees"
    expected_recommendations:
      - rule_id: "R-PHARMA-AI-001"
        action: "absent"
      - rule_id: "R-SME-EXEMPT-003"
        action: "present"
```

**运行方式：**
```bash
pytest tests/test_rules.py --rule-dir=pathfinder/rules/
# 自动发现所有 .test.yaml 文件，逐一验证
```

---

## 第六部分：性能基准

### pytest-benchmark 关键指标

```python
# tests/benchmark/test_graph_perf.py
def test_shortest_path_200_nodes(benchmark, large_graph):
    """200-node DAG — Apache AGE must complete <100ms, NetworkX <5s."""
    solver = PathfinderSolver(large_graph)
    result = benchmark(solver.plan_path, node_start, node_end, test_state)
    assert result.cost < float('inf')

def test_compliance_check_50_rules(benchmark, state_with_50_rules):
    """50 WP8 constraints — must complete <10ms."""
    result = benchmark(solver._is_compliant, test_state, test_node)
    assert result is True
```

---

## 第七部分：WP3 应急方案 (Plan B)

### 数据提取层 (Data Extraction Layer)

当 WP3 (CHARITE) 无法按时提供结构化路线图数据时，Pathfinder 通过独立的数据提取层从非结构化文档中获取所需数据：

```
┌─────────────────────────────────────────────────┐
│                  WP3 Plan B                      │
├─────────────────────────────────────────────────┤
│  Data Source Layer                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ JSON API │ │ CSV/TSV  │ │ Unstructured     │ │
│  │ (happy)  │ │ Export   │ │ (PDF, DOCX, MD)  │ │
│  └────┬─────┘ └────┬─────┘ └────────┬─────────┘ │
│       │            │               │            │
│       ▼            ▼               ▼            │
│  ┌─────────────────────────────────────────────┐ │
│  │         Extraction Service                   │ │
│  │  • Structured: direct mapping                │ │
│  │  • Semi-structured: regex + tabular parser   │ │
│  │  • Unstructured: LLM-assisted extraction     │ │
│  │    (nodes, edges, prerequisites, metadata)   │ │
│  └────────────────────┬────────────────────────┘ │
│                       │                          │
│                       ▼                          │
│  ┌─────────────────────────────────────────────┐ │
│  │         Validation & Normalization           │ │
│  │  • DAG cycle check                           │ │
│  │  • Schema compliance                         │ │
│  │  • Missing prerequisite detection            │ │
│  └────────────────────┬────────────────────────┘ │
│                       │                          │
│                       ▼                          │
│              pathfinder.core.graph               │
└─────────────────────────────────────────────────┘
```

### 优雅降级策略 (Graceful Degradation)

当上游数据不完整时，Pathfinder 不应完全失败，而是按以下优先级降级运行：

| 缺失数据 | 降级行为 | 用户可见影响 |
|----------|----------|-------------|
| WP3 维度标签缺失 | 节点仍可路由，但分类过滤不可用 | "Filter by dimension" 按钮灰显 |
| WP3 成熟度级别缺失 | 默认假设 maturity_level=1 | 路径可能非最优，但可执行 |
| WP3 前提条件缺失 | 标记为 optional，允许跳过 | 控制台警告 "unverified prerequisites" |
| WP2 利益相关者类型不全 | 使用通用问卷模板 | 特定行业的定制问题不可用 |
| WP8 规则文件缺失 | 合规检查降级为 pass-through | 所有节点标记为 "compliance unverified" |
| 全部上游缺失 | 退化到 demo 模式（mock 数据） | Banner: "DEMO MODE — not for production" |

**降级日志：** 所有降级事件写入 `audit_log`（event_type='graceful_degradation'），确保可追溯哪些决策是在数据不完整时做出的。

---

## 附录 A：IP_BOUNDARY.md 参考

逐文件所有权清单定义在 [IP_BOUNDARY.md](IP_BOUNDARY.md)，关键划分原则：

| 代码层级 | 所有权 | 许可 |
|----------|--------|------|
| `pathfinder/core/graph.py` | DataWego Background IP | 项目内免版税使用 |
| `pathfinder/core/solver.py` | DataWego Foreground IP | Epidata 永久使用许可 |
| `pathfinder/adapters/wp3_roadmap.py` | 双方共有 | 非竞争场景自由使用 |
| `pathfinder/adapters/wp8_compliance.py` | 双方共有 | 非竞争场景自由使用 |
| `migrations/*.sql` | DataWego Foreground IP | Epidata 永久使用许可 |
| `frontend/` | DataWego Foreground IP | Epidata 永久使用许可 |
| `tests/` | DataWego Foreground IP | Epidata 永久使用许可 |
| `rules/*.yaml` | WP8 提供，DataWego 工程化 | SCAILED 联盟内共享 |

*扩展分析完。与九龙决议合并，形成完整项目方案。*
*路径: ~/projects/scailed_wp4/council_debate_20260513/*

---

## 附录 B：Action Writeback — 推荐闭环反馈（2026-05-15 议会裁决）

### 问题

当前 Pathfinder 输出推荐后是黑洞。用户是否执行了"建立 DPO"的建议？半年后合规状态是否变化？系统不知道。

### 设计：推荐生命周期状态机

每条推荐从静态字符串升级为有生命周期的 Action 对象：

```
   ISSUED ──→ ACCEPTED ──→ IN_PROGRESS ──→ COMPLETED
     │            │              │
     └──→ SKIPPED │              └──→ BLOCKED
                  └──→ DEFERRED
```

| 状态 | 含义 | 触发方式 |
|------|------|----------|
| ISSUED | 系统生成，尚未被用户审阅 | 自动 |
| ACCEPTED | 用户确认采纳 | 用户点击 |
| SKIPPED | 用户跳过（附原因） | 用户点击+原因 |
| DEFERRED | 用户推迟到以后 | 用户点击+日期 |
| IN_PROGRESS | 执行中 | 用户标记或自动检测 |
| COMPLETED | 已完成 | 用户确认 |
| BLOCKED | 遇到障碍 | 用户报告+障碍描述 |

### 数据库扩展

```sql
CREATE TABLE action_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES assessment_sessions(id),
    recommendation_id UUID NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('issued','accepted','skipped','deferred','in_progress','completed','blocked')),
    reason TEXT,                    -- 跳过/推迟/受阻原因
    deferred_until TIMESTAMPTZ,     -- 推迟到何时
    changed_by TEXT,                -- 谁改变的（用户ID或'system'）
    changed_at TIMESTAMPTZ DEFAULT now(),
    previous_state TEXT,            -- 审计追踪
    metadata JSONB                  -- 扩展字段
);

-- 不可变审计
CREATE TRIGGER action_states_audit
BEFORE UPDATE OR DELETE ON action_states
FOR EACH ROW EXECUTE FUNCTION audit_log_no_mutation();
```

### Dijkstra形式化护栏

Action Types必须满足：

1. **Guarded transitions**: 每个状态转移有前置条件。例如 ISSUED→COMPLETED 非法（必须经过IN_PROGRESS）。
2. **Transactional isolation**: writeback与推荐引擎并发安全。写入action_states不阻塞solver。
3. **Deterministic state machine**: 状态转移图是确定性的——同一输入+同一状态=同一合法下一状态集合。

```python
# core/actions.py
from enum import Enum
from typing import Set

class ActionState(Enum):
    ISSUED = "issued"
    ACCEPTED = "accepted"
    SKIPPED = "skipped"
    DEFERRED = "deferred"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"

TRANSITIONS: dict[ActionState, Set[ActionState]] = {
    ActionState.ISSUED: {ActionState.ACCEPTED, ActionState.SKIPPED, ActionState.DEFERRED},
    ActionState.ACCEPTED: {ActionState.IN_PROGRESS, ActionState.SKIPPED, ActionState.DEFERRED},
    ActionState.IN_PROGRESS: {ActionState.COMPLETED, ActionState.BLOCKED},
    ActionState.SKIPPED: {ActionState.ACCEPTED},
    ActionState.DEFERRED: {ActionState.ACCEPTED, ActionState.SKIPPED},
    ActionState.COMPLETED: set(),    # 终态
    ActionState.BLOCKED: {ActionState.IN_PROGRESS, ActionState.SKIPPED},
}

def can_transition(from_state: ActionState, to_state: ActionState) -> bool:
    return to_state in TRANSITIONS.get(from_state, set())
```

### 闭环反馈路径

```
用户填问卷 → Solver生成推荐 → 用户标记执行状态 → 
写入action_states → 下次评估时solver读取历史 →
已完成推荐降低对应节点的edge cost → 推荐更精准
```

### 对D4.1的影响

Phase 3前端增加"推荐状态面板"：每条推荐旁显示当前状态+操作按钮（✓接受 / ⏭跳过 / ⏰推迟 / 🚧受阻）。D4.1 Demo需展示完整闭环。

---

*议会裁决日期: 2026-05-15 · 参与席位: Musk/Dijkstra/Linus/Guido/Jobs/Xuefeng/Xiaolong/FengGe*
