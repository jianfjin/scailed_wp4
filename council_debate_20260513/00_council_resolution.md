# SCAILED WP4 Pathfinder System — 九龙议会终论决议

**项目**: DataWego (乙方) 为 Epidata (甲方) 开发 SCAILED WP4 Pathfinder System
**日期**: 2026-05-13 (初议) / 2026-05-14 (六席审计修订) / 2026-05-15 (前端+数据库辩论 + Agent-D方案对比裁决)
**议会**: 9席全会 (Musk/Xuefeng/Guido/Dijkstra/Jensen/Jobs/Linus/Xiaolong/FengGe)
**审计**: 6席复审 (Xuefeng/Musk/Jobs/Linus/Guido/Dijkstra)
**辩论**: 前端5席 + 数据库5席 + Agent-D对比8席 (Musk/Linus/Dijkstra/Guido/Xiaolong/Xuefeng/Jobs/Jensen)
**项目周期**: EU4Health SCAILED, M1-M36

> **2026-05-15 最终融合裁决 (8/8全票)**:
> 陛下委托Agent-D产出的独立方案(docs/, 11份文档)与议会方案进行了8席位全面对比辩论。
> **吸收**: 立即开工不等数据(M0启动)、Mock数据先行(HL7 FHIR标准)、WP边界数据契约(写入合同附件)、产品化UX思维、本体论为头等工件。
> **维持**: PG+AGE(否决Neo4j, Dijkstra加V2日落条款)、Docker Compose(否决K8s)、3模块D4.1范围(否决AI Copilot/GraphRAG)、单repo(否决4-5 repos拆分)、确定性规则引擎(否决LLM路径评分)。
> **Agent-D方案成本估算**: €260K-320K (Xuefeng审计), 超出€145K预算80-120%。Agent-D方案是好产品蓝图，但不是€145K预算能交付的方案。

> **审计修订说明**: 2026-05-14 六席联合审计发现17个风险点（7个🔴致命），以下决议已全部吸收审计修正：
> IP条款重写、图引擎选型修正、付款结构加固、WP3数据Plan B、审计日志加固、规则引擎重构、邮件措辞修正、时间表压缩。
> 完整审计报告见文档 10-16。

---

## 议会共识：Pathfinder 的技术定义

Pathfinder = 带约束的图搜索（CSP框架）+ 问卷界面。不是 Web App，不是仪表盘，不是"平台"。

| 组件 | 是什么 | 不是什么 |
|------|--------|----------|
| 核心 | 约束满足问题（CSP）——带WP8法规剪枝的图搜索 | GPT 聊天机器人 / A*（无可采纳性证明不声称） |
| 输入 | 结构化问卷 + WP3路线图(DAG) + WP8法规(声明式规则) | PDF/PPT 手工解析 |
| 输出 | 可解释的确定性路径，每条建议可追溯到规则链 | 自然语言段落 / 黑箱概率建议 |
| 界面 | 交互式合规路径规划器：问卷 → 当前位置 → 推荐步骤 → 导出 | 炫酷仪表盘 |
| 定位 | 确定性、可审计的决策支持系统，超越EU AI Act透明度要求 | 防御性"不是AI" |

> **Dijkstra修正**: 这不是纯最短路径——路径可行性取决于(stakeholder, path)对，是CSP不是Dijkstra1959。S是有限离散配置文件集，不是ℝⁿ。A*不声称——无可采纳性证明不可信。

## 架构设计

三层单体：Vue 3 前端 → FastAPI 后端 → PostgreSQL（含Apache AGE图引擎）

```
pathfinder/
├── core/           # 纯Python：Pydantic models, solver, compliance, graph
│   ├── models.py   # 类型系统（审计要求：必须存在）
│   ├── solver.py   # 约束图搜索（AGE primary, NetworkX fallback）
│   ├── rules/      # 规则DSL：parser, validator, compiler, loader
│   └── exceptions/ # PathfinderError层级
├── api/            # FastAPI：routes, schemas, dependencies
├── services/       # 业务编排层（审计要求：路由与core间解耦）
├── adapters/       # WP2/3/5/6/7/8 数据适配器
├── migrations/     # Alembic（审计要求：必须存在）
├── config/         # Pydantic Settings（审计要求：替代裸os.environ）
├── scripts/        # 数据导入、规则校验
├── frontend/       # Vue 3 SPA（审计要求：移出Python package至repo根）
├── tests/          # pytest + fixtures + conftest
│   ├── fixtures/   # 共享mock数据
│   └── conftest.py
├── deploy/         # Docker Compose, Nginx配置
└── IP_BOUNDARY.md  # 逐文件版权归属（审计要求）
```

- **No 微服务, No K8s, No Neo4j, No GraphQL**
- **Docker Compose 多容器部署** (5 services: traefik + frontend(nginx+Vue) + backend(FastAPI) + postgres(PG16+AGE) + redis)
- **PostgreSQL 独立容器 + named volume** — 绝不与应用容器合署，这是 Docker 铁律
- 规则引擎外部化 (YAML/JSON，带JSON Schema静态校验), 热加载(API触发+watchdog)
- 审计日志: PostgreSQL TRIGGER（非RULE）+ prev_hash加密链式哈希
- 图引擎: **Apache AGE (PG原生图扩展，Cypher嵌入SQL)** + NetworkX作为开发/测试fallback
- 规则结构: recommendation_rules 树结构 (parent_rule_id + rule_type枚举 + priority)
- 完整部署配置见 `deploy/docker-compose.yml` + `deploy/Dockerfile.*`

## 技术栈

| 层 | 选型 | 审计修正 |
|----|------|----------|
| 语言 | Python 3.12 | — |
| 后端 | FastAPI + Pydantic v2 | NetworkX需ThreadPoolExecutor避免阻塞事件循环 |
| 规则引擎 | 声明式 YAML → Python 规则类 | 补：condition操作符全集JSON Schema + 冲突消解策略 + .test.yaml |
| 数据库 | PostgreSQL 16+ | — |
| 图引擎 | **Apache AGE** (primary) + NetworkX (dev) | 审计修正：纯NetworkX在200+节点时突破SLA |
| 前端 | React 19 (Primary) / Vue 3 (Alternative) + TypeScript | 2026-05-15修订: 前端选型待CHARITE确认。React主导欧盟市场(245K★/132M周下载), Vue适合非前端团队。DataWego两种均可交付。 |
| 部署 | Docker Compose | V1单机模式；K8s是V2的事 |
| 测试 | pytest + hypothesis + pytest-benchmark | 外壳≥80%，内核≥98%；mutation testing验证 |

## 子项目拆分

| Phase | 时间 | 内容 | 优先级 | 审计修正 |
|-------|------|------|--------|----------|
| Phase 0: 形式化基线 | M1-M3 | Schema确认 (WP2/3/8) + 数据提取层 + 代码骨架 | 🔴 生死线 | 加：M3未签自动延至M5 |
| Phase 1: 核心引擎 | M4-M8 | CSP引擎(AGE) + 约束检查 + 问卷引擎 | 🔴 | 压缩1个月；AGE引入 |
| Phase 2: API + 前端MVP | M9-M14 | FastAPI + Vue 3 前端 | 🟡 | — |
| Phase 3: V1交付 | M15-M20 | 打磨 + 报告支持 | 🟡 | — |
| Phase 4: Test Drive | M21-M24 | T4.2 验证反馈 (CHARITE-led) | 🟢 | DataWego仅修bug |
| Phase 5: V2迭代 | M25-M33 | D4.4 最终指南 (CHARITE-led) | 🟢 | 独立合同 |

> **Musk修正**: MVP可3-4月完成。Phase 0-2从15个月压缩至14个月。省下时间用于真实用户测试、EHDS合规验证、实际图规模性能测试。

## 上下游数据交换

**DataWego 需要**:
- WP3 路线图 (JSON/CSV + 拓扑验证) — 阻塞级
- WP8 法规约束 (声明式规则/YAML) — 阻塞级
- WP2 利益相关者分类 (JSON Schema) — 阻塞级
- **WP3 Plan B**: 合同要求Epidata保证结构化交付或出资数据提取；Pathfinder以"最佳可用"数据运行，带置信标记

**DataWego 提供**: D4.1 Demo + 报告, REST API endpoints (含速率限制), Docker Compose 部署包, 加密链审计日志

## 核心风险（审计强化版）

| 风险 | 概率 | 影响 | 缓解 | 审计来源 |
|------|------|------|------|----------|
| WP3 交付 PDF 非结构化数据 | 极高 | 致命 | M2强制JSON格式 + **合同约束Epidata保证结构化交付或出资提取 + 数据提取层** | Musk, Jobs |
| WP8 法律不可形式化 | 高 | 高 | 软检查 + 规则热加载 + .test.yaml规则测试框架 | Guido |
| NetworkX性能崩溃(200+节点) | 高 | 致命 | **M4引入Apache AGE替代纯NetworkX** | Linus |
| EU4Health IP规则违规 | 高 | 致命 | **Background/Foreground分界 + IP_BOUNDARY.md逐文件版权** | Xuefeng, Guido |
| M9付款绑定CHARITE→现金流断裂 | 极高 | 致命 | **M9 15%+M15 15%拆分 + CHARITE拖款超30天Epidata先行垫付** | Xuefeng |
| Schema M3签不下来无延期 | 高 | 高 | **自动延至M5，付款顺延；上游变更按费率计费** | Xuefeng |
| 返工条款EUR-X/天留空 | 高 | 高 | **三档费率 + 书面审批流程 + 上限(单次≤15%, 全年≤30%)** | Xuefeng |
| 审计日志RULE不可靠 | 中高 | 中 | **RULE→TRIGGER + prev_hash加密链** | Linus, Guido |
| EHDS实施细则中途变更 | 中高 | 中 | 规则引擎热加载 + rule_versions表 | — |

## 合同框架（审计强化版）

### IP条款
- **Background IP**: DataWego在项目前独立研发的底层图搜索算法（IP_BOUNDARY.md逐文件定义）归DataWego所有
- **Foreground IP**: SCAILED项目期间针对EU4Health需求的定制化开发归项目联盟共有
- DataWego获得项目外商业化的优先谈判权（12个月内）
- 许可：Apache-2.0或MIT（非GPL/AGPL）

### 付款结构
- 预付款 30% (合同签署后15日)
- M9 15% (核心引擎交付) + M15 15% (MVP交付) — **拆分自原M9 30%**
- D4.1 尾款 40% (M20验收通过)
- CHARITE拖款超30天 → Epidata先行垫付

### 返工条款
- 三档费率：架构师 €800-1200/天，高级开发 €600-800/天，初级开发 €400-600/天
- 流程：书面提出变更 → DataWego评估人天 → 双方书面确认 → 开始返工
- 上限：单次 ≤15%合同总额，全年 ≤30%
- Schema基线范围内精炼包含在固定价格中（M3基线锁定后的结构性变更才触发返工）

## 峰哥战略裁决

1. **内核搞扎实** (AGE图搜索+CSP引擎+加密审计链，内核≥98%覆盖率)
2. **外壳搞漂亮** (前端UI+演示录屏+PDF报告，外壳≥80%覆盖率)
3. **基线先确认再开工** (M3前双方共同确认Schema基线；M3未签自动延至M5)
4. **合同护城河** (Background/Foreground IP分界, 付款拆分, 三档返工费率, 垫付条款)
5. **技术只做减法** (Xiaolong MVP清单)
6. **数据不依赖祷告** (WP3 Plan B：合同约束+提取层+降级策略)
7. **措辞建桥不筑墙** (合作语气：共同基线、双方确认、协同校准)

> **Jobs的一刀**: "Pathfinder不是帮你填合规表格。它让合规变成直觉。"

---

*存档: ~/projects/scailed_wp4/council_debate_20260513/00_council_resolution.md*
*完整议政录见 01-08 号文件 · 审计报告见 10-16 号文件*
*审计修订日期: 2026-05-14*
