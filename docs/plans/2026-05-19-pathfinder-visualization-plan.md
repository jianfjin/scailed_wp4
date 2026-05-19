# Pathfinder 结果可视化 — 实施方案

**日期**: 2026-05-19  
**Branch**: feature/1000-mock-records  
**问题**: Pathfinder 的 JSON 输出难以理解。需要可视化 audit chain、roadmap nodes、推理链和证据。

---

## 当前输出现状

GET `/v1/assessments/{id}/report` 返回的 JSON：

```json
{
  "recommended_path": {
    "status": "blocked",
    "next_steps": [{node_id, label, dimension, maturity_level}],
    "blockers": ["legal-basis: GDPR review required"],
    "triggered_rules": [{rule_id, condition, action, compliance_refs}],
    "trace": {
      "answer_ids": [...],
      "roadmap_node_ids": [...],
      "triggered_rule_ids": [...],
      "regulatory_refs": [...]
    },
    "path_backend": "python"
  },
  "audit_chain_valid": true
}
```

问题：
- `next_steps` 是扁平列表，看不出图结构（哪个节点依赖哪个）
- `triggered_rules` 不知道为什么这些规则触发了
- `trace` 只是 ID 列表，没有解释
- `blockers` 不知道跟哪些规则/节点相关

---

## 可视化方案：三个视图

### 视图 1: Audit Chain（审核链）

**目标**: 展示 answers → rules → nodes → recommendation 的完整推理链

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  ANSWERS     │    │  RULES       │    │  NODES       │    │  OUTCOME     │
│              │    │              │    │              │    │              │
│ governance=2 ├───►│ GDPR-REVIEW  ├───►│ legal-basis  │    │ BLOCKED      │
│ data=2       │    │ (triggered)  │    │ (activated)  ├───►│              │
│ compliance=2 │    │              │    │              │    │ Next:        │
│ regulatory=  │    │ DATA-CATALOG ├───►│ gov-scope    │    │ legal-basis  │
│  gdpr-review │    │ (triggered)  │    │ (activated)  │    │              │
│ missing=     │    │              │    │              │    │ Confidence:  │
│  data-catalog│    │              │    │              │    │ 0.85         │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

每一段连接可展开看证据：
- Answers → Rule: 展示 condition match（field=regulatory_flags, operator=contains, value=gdpr-review-needed）
- Rule → Node: 展示 action（title, text, node_id, warning）
- Evidence: 展示 source_doc_ref, compliance_refs

### 视图 2: Roadmap Graph（路线图）

**目标**: 展示合规路线图 DAG，高亮已走路径、标注阻塞点

```
     ┌─────────┐
     │ generic  │  ✓ 已完成
     │ -intake  │
     └────┬────┘
          │
     ┌────▼────┐
     │ gov-     │  ✓ 已完成
     │ scope    │
     └────┬────┘
          │
     ┌────▼────┐
     │ legal-   │  ✗ 阻塞
     │ basis    │  ← GDPR-REVIEW-001
     └────┬────┘  ← DATA-CATALOG-GAP-003
          │
     ┌────▼────┐
     │ secure-  │  ○ 未到达
     │ process  │
     └─────────┘
```

颜色编码：
- 绿色 = 已完成（answers 满足 maturity 要求）
- 红色 = 阻塞（有 blocker，标注触发的 rule）
- 灰色 = 未到达
- 蓝色 = 当前节点

### 视图 3: Evidence & Reasoning（证据与推理）

**目标**: 解释每条规则的触发原因

每个 triggered rule 展示一个证据卡片：

```
┌─ Rule: WP8-GDPR-REVIEW-001 ────────────────────────┐
│ Priority: 100  │  Type: preference                  │
│                                                     │
│ Condition:                                           │
│   field=regulatory_flags                             │
│   operator=contains                                  │
│   value=gdpr-review-needed                           │
│                                                     │
│ Your answers:                                        │
│   regulatory_flags = [gdpr-review-needed]  ← MATCH   │
│                                                     │
│ Action:                                              │
│   "Confirm GDPR and ethics review inputs before      │
│    downstream data access."                          │
│   → Routes to node: legal-basis                      │
│                                                     │
│ Compliance References:                               │
│   • GDPR-Review                                      │
│   • EHDS-Secondary-Use                               │
│                                                     │
│ Source: docs/12_merged_pathfinder_spec.md#F5         │
└─────────────────────────────────────────────────────┘
```

---

## 实现清单

### Phase 1: 数据适配层 (0.5d)

**目标**: 把现有 JSON 输出转换成可视化友好的结构

新增 `pathfinder/visualization/adapter.py`:
```python
def build_audit_chain(recommendation: dict) -> dict:
    """answers → rules → nodes → outcome 的链接表"""
    
def build_graph_state(recommendation: dict) -> dict:
    """节点状态 (completed/blocked/unreached) + 边高亮"""
    
def build_evidence_cards(recommendation: dict) -> list[dict]:
    """每条 triggered rule 的证据卡片数据"""
```

### Phase 2: Audit Chain 可视化 (1d)

**目标**: 自包含 HTML，左侧 answers，中间 rules，右侧 nodes

文件: `pathfinder/visualization/templates/audit-chain.html`

技术选型: 纯 HTML/CSS/SVG，无 JS 框架
- 使用 html-spec 风格（ivory 背景）
- SVG 箭头连接三段
- Collapsible evidence panels
- 移动端 responsive

输出路径: `GET /v1/assessments/{id}/report?format=html`

### Phase 3: Roadmap Graph 可视化 (1.5d)

**目标**: DAG 展示，路径高亮，阻塞标注

文件: `pathfinder/visualization/templates/roadmap-graph.html`

技术选型: SVG 手动布局（无 d3/vis.js）
- 分层布局（maturity level 1-5 从左到右）
- 已完成节点绿色，当前节点蓝色，阻塞节点红色
- hover tooltip 显示节点详情
- 点击展开 rule 触发信息

### Phase 4: Evidence Cards (0.5d)

**目标**: 每条规则一卡，展开/折叠

文件: `pathfinder/visualization/templates/evidence-cards.html`

- 规则触发条件 vs 用户实际答案对比
- Compliance reference 外链
- Source document 引用
- 绿色边框 = 匹配，灰色 = 未匹配

### Phase 5: 集成 Panel (1d)

**目标**: 一个 HTML 文件包含全部三个视图，tab 切换

文件: `pathfinder/visualization/templates/report-panel.html`

```
┌─────────────────────────────────────────────┐
│  [Audit Chain] [Roadmap Graph] [Evidence]   │ ← tabs
├─────────────────────────────────────────────┤
│                                              │
│         当前视图内容                           │
│                                              │
└─────────────────────────────────────────────┘
```

底部状态栏: audit_chain_valid, confidence, path_backend

### Phase 6: FastAPI 端点 (0.5d)

新增路由:
- `GET /v1/assessments/{id}/visualize` → 重定向到 HTML
- `GET /v1/assessments/{id}/visualize?view=audit` → 默认 audit chain
- `GET /v1/assessments/{id}/visualize?view=graph` → roadmap graph  
- `GET /v1/assessments/{id}/visualize?view=evidence` → evidence cards

---

## 工作量汇总

| Phase | 内容 | 估时 |
|-------|------|------|
| P1 | 数据适配层 (adapter.py) | 0.5d |
| P2 | Audit Chain HTML | 1d |
| P3 | Roadmap Graph HTML | 1.5d |
| P4 | Evidence Cards HTML | 0.5d |
| P5 | 集成 Panel (tab切换) | 1d |
| P6 | FastAPI 端点 | 0.5d |
| **总计** | | **5d** |

---

## 技术约束

- **零外部依赖**: 纯 Python 生成 HTML/SVG，无 d3.js / vis.js / React
- **自包含**: 每个 HTML 文件可以直接在浏览器打开，无 CDN
- **复用 html-spec 风格**: ivory 背景, serif 标题, clay 强调色
- **复用 architecture-diagram 风格**: SVG routing, marker arrows, dark grid（roadmap graph）
- **与现有代码兼容**: adapter.py 从 recommendation dict 读取，不改 Pathfinder 核心

---

## 风险

| 风险 | 概率 | 缓解 |
|------|------|------|
| 1000 节点的 DAG 在 SVG 中不可读 | 中 | 提供 zoom/pan，或只显示路径相关子图 |
| SVG 布局算法复杂 | 中 | 分层布局（maturity level = x 坐标），用 BFS 定 y |
| 规则条件展示依赖模型理解 | 低 | adapter 已抽象 condition→自然语言 |
