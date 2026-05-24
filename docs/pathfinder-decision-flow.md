# SCAILED WP4 Pathfinder — 决策流程文档

**日期:** 2026-05-23  
**项目:** `~/projects/scailed_wp4`  
**相关文件:** `docs/13_merged_pathfinder_design.md`, `pathfinder/core/solver.py`, `pathfinder/services/assessment_service.py`

---

## 一、整体架构

Pathfinder 是一个**模块化单体**应用，核心决策引擎基于**有向图 BFS 搜索 + 规则引擎**。

```
Frontend (React) → FastAPI → InMemoryRoadmapGraph (或 PostgreSQL+AGE)
                    │
                    → RuleEngine + ComplianceEvaluator
                    → QuestionnaireEngine
                    → AuditLog (append-only)
```

## 二、数据来源（三个 WP 服务）

| 来源 | 端点 | 数据内容 | 用途 |
|------|------|---------|------|
| **WP2** | `GET /api/v1/stakeholders` | stakeholder_type, description | 生成问卷, 提供 stakeholder_type 作为图形过滤键 |
| **WP3** | `GET /api/v1/roadmap/nodes + /edges` | RoadmapNode + RoadmapEdge | 构建有向图 (nodes dict + adjacency list) |
| **WP8** | `GET /api/v1/rules` | Rule (condition, action, priority) | 规则引擎, 决策阻断/警告/偏好 |

## 三、启动阶段（数据加载）

```
UpstreamClient.startup()
  ├── fetch_stakeholders()  → 原始 dict → schema 归一化 → self.stakeholders
  ├── fetch_roadmap()       → JSON → RoadmapNode / RoadmapEdge → self.roadmap_nodes/edges
  └── fetch_rules()         → JSON → Rule 领域模型 → self.rules

AssessmentService.__init__(upstream_client)
  ├── _load_upstream_data(client)
  │     WP2: stakeholder_type → Questionnaire (每个类型一份问卷)
  │     WP3: nodes + edges → self._active_roadmap
  │     WP8: rules → self.rules
  │
  ├── 构建图: InMemoryRoadmapGraph(nodes, edges)
  │     ├── self.nodes = {node_id: RoadmapNode}  ← O(1) 查找
  │     ├── self.edges = [RoadmapEdge, ...]      ← 原始边列表
  │     └── self._outgoing = {from: [to, ...]}   ← 邻接表
  │
  └── 构建求解器: PathfinderSolver(graph)
```

## 四、运行时决策流程

### 步骤 1: 用户选择 Stakeholder

```
GET /v1/questionnaires/{stakeholder_type}
  → QuestionnaireEngine.get(stakeholder_type)
  → 返回该 stakeholder 的问卷 (问题列表 + 目标场景)
```

WP2 的数据在此处用途: `stakeholder_type` 作为问卷分发的键。

### 步骤 2: 用户提交答案

```
POST /v1/assessments/{id}/answers/batch
  → QuestionnaireEngine.build_state(stakeholder_type, target_scenario, answers)
  → 生成 StakeholderState:
      - stakeholder_type    (如 "biotech-sme")
      - target_scenario     (如 "ehds-compliance")
      - maturity_scores     (由答案推导: {"governance": 2, "data": 1, "compliance": 3})
      - answers             (原始答案 dict)
      - confidence          (可信度)
```

### 步骤 3: 请求推荐 — solver.solve(state, rules)

这是核心决策环节，顺序如下:

#### 3a. 定位当前节点 — `graph.locate_current(state)`

```python
def locate_current(self, state: StakeholderState) -> RoadmapNode:
    # 1. 按 stakeholder_type 过滤可见节点
    applicable = self.applicable_nodes(state.stakeholder_type)
    # 2. 按 maturity 维度打分，选最近匹配的
    #    分数 = abs(成熟度 - 节点等级)
    return sorted(applicable, key=score)[0]
```

**关键**: WP2 的 stakeholder_type **不作为节点加入图**，而是作为**过滤条件**筛选图上哪些节点对这个用户可见。

```python
def applies_to(self, stakeholder_type: str) -> bool:
    return stakeholder_type in self.stakeholder_types or "all" in self.stakeholder_types
```

#### 3b. 定位目标节点 — `graph.locate_target(state)`

```python
def locate_target(self, state: StakeholderState) -> RoadmapNode:
    applicable = self.applicable_nodes(state.stakeholder_type)
    # 按 target_scenario 匹配 metadata
    # 如果没有匹配，选最高 maturity 的节点
    return sorted(candidates, key=lambda n: n.maturity_level, reverse=True)[0]
```

#### 3c. 规则预检 — `evaluator.triggered_rules(state, rules)`

**这是用户理解中需要纠正的关键点**: 规则检查发生在**路径搜索之前**，不是之后。

```
triggered_rules(state, rules):
  for each rule in rules:
    1. 检查 rule.applies_to(stakeholder_type)  ← 同样按 stakeholder 过滤
    2. 检查 rule.condition(state)               ← 条件表达式树
       (支持: eq, ne, gt, gte, lt, lte, in, not_in, contains, and, or, not)
    3. 如果匹配 → 加入 triggered 列表
    4. 检查 rule.action:
       - action.block = True → 加入 blockers
       - action.warning → 加入 warnings
       - action.node_id → 特定节点建议
```

#### 3d. BFS 最短路径搜索 — `graph.shortest_path(current, target)`

```python
def shortest_path(self, start_node_id, target_node_id):
    # BFS (广度优先)
    queue = deque([(start_node_id, [start_node_id])])
    seen = {start_node_id}
    while queue:
        current, path = queue.popleft()
        if current == target_node_id:
            return tuple(self.nodes[nid] for nid in path)
        for next_node in self._outgoing.get(current, []):
            if next_node not in seen:
                seen.add(next_node)
                queue.append((next_node, [*path, next_node]))
    # 无路径 → NoFeasiblePathError
```

**注意**: 即使有 blocker 也继续搜索路径（用于前端展示完整图谱）。只有在路径真正不存在时才抛出异常。

#### 3e. 合并结果 — PathResult

```python
return PathResult(
    current_node=current.node_id,
    target_node=target.node_id,
    steps=steps,                  # BFS 路径节点列表
    blockers=blockers,            # 阻断规则（来自规则预检）
    warnings=warnings,            # 警告（来自规则 + 置信度）
    triggered_rules=triggered,    # 所有触发的规则
    confidence=state.confidence,  # 置信度
    trace=TraceRecord(            # 审计追踪
        answer_ids=...,
        roadmap_node_ids=...,
        triggered_rule_ids=...,
        regulatory_refs=...,
        ...
    )
)
```

## 五、完整数据流（端到端）

```
Startup:
  WP2 ──GET──→ UpstreamClient ──stakeholder_type──→ QuestionnaireEngine
  WP3 ──GET──→ UpstreamClient ──nodes+edges───────→ InMemoryRoadmapGraph
  WP8 ──GET──→ UpstreamClient ──rules─────────────→ RuleLoader

Runtime:
  User ──选择stakeholder──→ QuestionnaireEngine ──返回问卷──→ User
  User ──提交答案────────→ build_state() ──→ StakeholderState

  PathfinderSolver.solve(state, rules):
    │
    ├── 1. graph.applicable_nodes(stakeholder_type)  ← FILTER
    │      └── stakeholder_type 过滤图上哪些节点可见
    │
    ├── 2. graph.locate_current(state)  ← 找当前位置
    │
    ├── 3. graph.locate_target(state)   ← 找目标位置
    │
    ├── 4. evaluator.triggered_rules(state, rules)  ← 规则预检（先于路径）
    │      ├── 无 blocker → 正常
    │      └── 有 blocker → 记录阻断，但继续搜索路径
    │
    ├── 5. graph.shortest_path(current, target)  ← BFS
    │
    └── 6. 组装 PathResult → build_recommendation() → 返回给前端
```

## 六、关键纠正（vs 用户最初的理解）

| 用户的理解 | 实际代码行为 | 差异 |
|-----------|-------------|------|
| WP2 数据注入图作为节点 | stakeholder_type 作为**过滤键**筛选图上节点 | WP2 数据不入图，只做路由 |
| 搜索完成后与 rules 比对 | **规则先于路径搜索触发**，然后才做 BFS | 顺序反了 |
| blocker 阻断路径搜索 | blocker 只影响推荐结果，路径搜索继续执行 | blocker 阻断推荐，不阻断搜索 |
| 所有数据都在 AGE 图里 | 实际查询层是**内存 dict**（self.nodes），AGE 是 V2 预备 | 当前是纯 Python BFS |

## 七、降级策略

| 缺失输入 | 行为 |
|---------|------|
| WP2 无数据 | 使用通用问卷模板，标记低置信度 |
| WP3 无数据 | 使用 demo_data.py 硬编码节点/边 |
| WP8 无数据 | compliance 标记为 "unverified" |
| AGE 不可用 | 降级到 InMemoryRoadmapGraph，confidence=0.0 |
| 全部缺失 | 纯 Demo 模式运行 |
