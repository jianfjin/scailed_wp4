# SCAILED WP4 Pathfinder System — 九龙议会终论决议

**项目**: DataWego (乙方) 为 Epidata (甲方) 开发 SCAILED WP4 Pathfinder System
**日期**: 2026-05-13
**议会**: 9席全会 (Musk/Xuefeng/Guido/Dijkstra/Jensen/Jobs/Linus/Xiaolong/FengGe)
**项目周期**: EU4Health SCAILED, M1-M36

---

## 议会共识：Pathfinder 的技术定义

Pathfinder = 带约束的图搜索引擎 + 问卷界面。不是 Web App，不是仪表盘，不是"平台"。

| 组件 | 是什么 | 不是什么 |
|------|--------|----------|
| 核心 | 有约束的图搜索问题 (Dijkstra/A*) | GPT 聊天机器人 |
| 输入 | 结构化问卷 + WP3路线图 + WP8法规 | PDF/PPT 手工解析 |
| 输出 | 带审计追踪的形式化推荐路径 | 自然语言段落 |
| 界面 | 极简问卷 → 定位 → 路径 → 行动 | 炫酷仪表盘 |

## 架构设计

三层单体：Vue 3 前端 → FastAPI 后端 (Assessment Engine + Recommendation Engine + Compliance Adapter + WP Adapters) → PostgreSQL (JSONB + 审计日志)

- **No 微服务, No K8s, No Neo4j, No GraphQL**
- **Docker Compose 单容器部署**
- 规则引擎外部化 (YAML/JSON), 热加载
- Python package: core/ api/ adapters/ frontend/ tests/

## 技术栈

| 层 | 选型 | 
|----|------|
| 语言 | Python 3.12 |
| 后端 | FastAPI + Pydantic v2 |
| 规则引擎 | 声明式 YAML → Python 规则类 |
| 数据库 | PostgreSQL (JSONB) |
| 前端 | Vue 3 + Vite |
| 部署 | Docker Compose |
| 测试 | pytest + hypothesis |
| 图算法 | NetworkX |

## 子项目拆分

| Phase | 时间 | 内容 | 优先级 |
|-------|------|------|--------|
| Phase 0: 形式化冻结 | M1-M3 | Schema 签字 (WP2/3/8) | 🔴 生死线 |
| Phase 1: 核心引擎 | M4-M9 | Assessment + Recommendation Engine | 🔴 |
| Phase 2: API + 前端MVP | M10-M15 | 可演示版 (D4.2 M18) | 🟡 |
| Phase 3: V1交付 | M16-M20 | D4.1 Pathfinder V1/demo | 🟡 |
| Phase 4: Test Drive | M21-M24 | T4.2 验证反馈 | 🟢 |
| Phase 5: V2迭代 | M25-M33 | D4.4 最终指南 | 🟢 |

## 上下游数据交换

**DataWego 需要**: WP3 路线图 (JSON/CSV + 拓扑排序), WP8 法规约束 (布尔谓词/YAML), WP2 利益相关者分类 (JSON Schema) — 全部 M3 前锁定

**DataWego 提供**: D4.1 Demo + 报告, REST API endpoints, Docker Compose 部署包, 审计日志

## 核心风险

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| WP3 交付 PDF 非结构化数据 | 极高 | 致命 | M2 强制 JSON 格式 |
| WP8 法律不可形式化 | 高 | 高 | 软检查 + 规则热加载 |
| 需求模糊反复返工 | 极高 | 高 | M1 原型签字 |
| EU 审计合规 | 低 | 极高 | 每次 commit 附合规注释 |
| EHDS 实施细则中途变更 | 中高 | 中 | 规则引擎热加载 |

## 峰哥战略裁决

1. 内核搞扎实 (图搜索+规则引擎+审计追踪，TDD)
2. 外壳搞漂亮 (前端UI+演示录屏+PDF报告)
3. 接口先锁死再开工 (M3 前无签字不开工)
4. 合同护城河 (预付款30%, 里程碑绑定上游, V2独立合同)
5. 技术只做减法 (Xiaolong MVP 清单)

---

*存档: ~/projects/scailed_wp4/council_debate_20260513/00_council_resolution.md*
*完整议政录见 01-08 号文件*
