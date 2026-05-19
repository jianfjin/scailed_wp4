# 议会辩论记录 — Pathfinder 可视化方案审计

**日期**: 2026-05-19
**议题**: 审议 `docs/plans/2026-05-19-pathfinder-visualization-plan.md`（Pathfinder 结果可视化方案）
**辩论子集**: Product + Architecture (Jobs/Musk/Guido/Linus/小龙/雪峰)
**决议**: 原方案 5d → 修正方案 2d, 6/6 反对原方案

---

## 一、原方案摘要

6 阶段, 5人天:
1. 数据适配层 (0.5d)
2. Audit Chain HTML (1d)
3. Roadmap Graph HTML SVG DAG (1.5d)
4. Evidence Cards HTML (0.5d)
5. 集成 Panel + tab 切换 (1d)
6. FastAPI 端点 (0.5d)

技术约束: 零外部依赖, 纯 Python→HTML/SVG, 三个独立 HTML 文件

---

## 二、各席位发言

### 1. Elon Musk (CVO, kimi-2.6, 37s) — 否决

> "Over-architected by a factor of five."
>
> 原方案在造 dashboard, 不是在解释 decision。delete 步骤: 砍掉 adapter 层, 砍掉 tab 切换, 砍掉独立 SVG DAG 库, 砍掉新端点。
> 最终产品: 一个 HTML 文件, 纵向四面板, 打印出来合规官能签字。
>
> **工作量**: 1d

### 2. Steve Jobs (CPO, kimi-2.6, 50s) — 否决

> "You're building a visualization layer, not an explanation layer."
>
> 缺三样东西:
> 1. 叙事线 — Humans understand stories, not diagrams. 从 "what's wrong" 到 "what to do Monday morning"
> 2. Readiness Score — 单数字, 不要一堆图。"That one number is what matters."
> 3. "What If" 模式 — 滑块改答案, 路径重算。"Interaction breeds trust."
>
> Blocker 必须是 actionable task: 法规原文 + trigger 原因 + owner + due date.

### 3. 张雪峰 (CSA, deepseek-v4-flash, 24s) — 否决, 成本审计

> 5天方案里有3天是"泡沫"。

| 阶段 | 方案估时 | 真实需要 | 差值 |
|------|---------|---------|------|
| 数据适配层 | 0.5d | 0d | +0.5 |
| SVG DAG | 1.5d | 0.25d (文本卡片) | +1.25 |
| 证据卡 | 0.5d | 0d (合并到 audit chain) | +0.5 |
| 集成面板 | 1d | 0.5d | +0.5 |
| FastAPI | 0.5d | 0.25d | +0.25 |
| **合计** | **5d** | **2d** | **+3d** |

> "SVG DAG 砍掉。用户看完的反应: '哦,有个图。' 然后回去看旁边的文本总结。我保证90%的用户不会说要看图。"

> MVP 方案: `/report?format=html`, 一个 HTML, 顶栏状态标签 + 阻塞卡片 + 下一步建议 + 文本路径流。

### 4. 张小龙 (Eng, deepseek-v4-pro, 69s) — 否决, 工程风险评估

> Phase 3 (SVG DAG, 1.5d) 是地雷。
> "纯手写布局, 光 crossing minimization 就够一篇硕士论文。"
> 折中: 用 graphviz 命令行生成 SVG, Python 后处理注入高亮。
> 证据卡片先做, 图往后放。

### 5. Guido van Rossum (CLA, kimi-2.6, 125s) — 否决, 数据模型审计

> `build_audit_chain(recommendation: dict)` — Dict[str, Any] 是定时炸弹。
> `build_graph_state` 需要完整 roadmap DAG, 不能从 recommendation 里提取。
> 缺 validation: 空规则列表, 旧版 assessment 缺 trace → KeyError。
>
> **插入一层 view model**: `dict → adapter → dataclass → template`。
> 先写 schemas.py, 再写 HTML。"Simple is better than complex."

### 6. Linus Torvalds (Arch, deepseek-v4-pro, 224s) — 有条件批准 SVG 方向

> "APPROVE the pure SVG approach. REJECT the adapter layer and phased file structure."
>
> 1000节点恐慌是 FUD — 在渲染子图, 不是全 DAG。
> zoom/pan 可以用纯 CSS `transform: scale()` + `overflow: scroll`。
> "如果有人把 estimate 从真实值 padding 到 5 天, 直接说出来。"
>
> **工作量**: 2.75d (P1+P2 合并 1.5d, P3 0.5d, P4 0.25d)

---

## 三、计票

| 席位 | 原方案 5d | 修正估算 | 核心理由 |
|------|----------|---------|----------|
| Musk | ❌ | 1d | One file, 4 panels |
| Jobs | ❌ | — | Missing narrative + What If |
| 雪峰 | ❌ | 2d | 3d padding identified |
| 小龙 | ❌ | 3d | DAG layout is a minefield |
| Guido | ❌ | — | Data contracts undefined |
| Linus | ⚠️ | 2.75d | Approve SVG, collapse phases |
| **CTO** | **❌** | **2d** | **Synthesis** |

**票数: 6/6 反对原方案**

---

## 四、议会决议

> **原可视化方案 (5d, 6 phase) 被否决。修正方案 (2d, 3 phase):**

```
Phase 1 (1d): 单 HTML generator
  GET /report?format=html → 自包含 HTML
  纵向四段:
    ① Readiness Score (大标签, 信心条)
    ② Blockers (红卡, 可展开条件证据)
    ③ Compliance Path (文本节点流, 颜色编码)
    ④ Evidence (可展开规则卡)
  数据流: dict → adapter → dataclass → template
  Guido view model layer 强制实施

Phase 2 (0.5d): Evidence 深挖
  每规则: condition match 高亮 + compliance refs + source doc

Phase 3 (0.5d): 路径图
  graphviz CLI → SVG, Python 后处理高亮
  限定路径子图 (非全量1000节点)
```

---

## 五、执行情况

| 事项 | 状态 |
|------|------|
| schemas.py (6 dataclasses) | ✅ |
| adapter.py (JSON→view model) | ✅ |
| renderer.py (HTML generator) | ✅ |
| FastAPI endpoint (?format=html) | ✅ |
| P3 路径图 (graphviz) | ⏳ |
| e2e 测试 | ⏳ |

---

**归档**: docs/records/2026-05-19-council-debate-visualization-plan.md
**签署**: 峰哥 (CTO, 议会召集人)
**日期**: 2026-05-19, The Hague
