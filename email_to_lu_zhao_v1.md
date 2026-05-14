From: Feng Ge / DataWego
To: Lu Zhao / EPIDATA
Subject: SCAILED WP4 Pathfinder System — 初步方案与下一步建议

赵总，您好。

感谢将 SCAILED WP4 Pathfinder System 的开发机会交给 DataWego。我们已仔细研读了 SCAILED 项目提案全文，对 WP4 的任务范围、交付物、上下游依赖和 Epidata 的角色做了深入分析。以下是我们对项目的理解和初步建议，供您审阅。

## 一、我们对 Pathfinder System 的理解

从技术本质上，Pathfinder 是一个带合规约束的战略定位与导航系统。利益相关者通过结构化自评问卷输入当前状态，系统对照 WP3 的战略路线图和 WP8 的法规框架，输出三样东西：

1. "你现在在哪"（路线图定位）
2. "往哪走"（优先级排序的行动建议）
3. "路上有哪些红绿灯"（合规风险标注）

这是个可解释的决策导航工具，不是黑箱 AI。核心是声明式规则引擎 + 图搜索算法，界面极简——类似于 Apple Setup Assistant 体验，不是 SAP Dashboard。

## 二、我们的技术方案

- 后端：Python + FastAPI + PostgreSQL
- 核心算法：基于 DAG 最短路径（Dijkstra），确保每条建议可审计追溯
- 规则引擎：YAML 外部化声明式规则，非程序员（您的 QA 团队）可直接审阅
- 前端：Vue 3，单页应用，问卷 → 地图 → 行动建议三步体验
- 部署：Docker Compose 单容器，CHARITE 可在自己服务器上一键部署
- 审计追踪：每次答案修改、每次推荐生成 → 不可篡改日志

## 三、我们需要在 M3（第三个月）前锁定的前置条件

Pathfinder 是数据驱动系统，不是独立 App。它的核心逻辑依赖三个上游输出：

1. **WP3 战略路线图**（CHARITE 负责）——需要机器可读的节点-边列表（JSON/CSV），附拓扑排序证明。如果是 PDF 格式的彩色箭头图，我们需要额外翻译层。
2. **WP8 法规框架**——需要可执行的规则描述（如 YAML 格式的 if-then 规则集）。"遵循 GDPR/EHDS 精神"级别的指导原则无法直接转化为合规检查器。
3. **WP2 利益相关者分类**——需要结构化的用户类型矩阵（JSON Schema）。

**我们的策略**：在等待上游数据时（M1-M3），用 mock 数据搭建系统骨架、问卷引擎、推荐引擎原型。M3 锁定数据 Schema 后，M4 开始对接真数据。这样不会因上游延迟而整体停工，但 Schema 必须在 M3 签字确认。

## 四、关于 SHAIPED

提案中提到您曾参与 SHAIPED 项目（WP4 Lead）。如果 SHAIPED 已有先验工作（代码库、方法论、数据模型），我们希望在 M1 进行一次审计——哪些可以复用，哪些建议重写。这可以大幅降低重复投入。

## 五、建议的推进步骤

| 时间 | 事项 |
|------|------|
| 合同签署前 | 三方（DataWego + Epidata + 贵方法务）确认范围、付款、验收条款 |
| M1 | Kick-off 会议 + SHAIPED 代码/文档审计 |
| M1-M2 | 我们做出三版低保真原型（交互式决策树 / 图导航 / 问卷流），您选定方向后签字确认 |
| M3 前 | WP2/WP3/WP8 数据 Schema 草案锁定并签字 |
| M4-M12 | 核心引擎开发 + 前端 MVP |
| M13-M18 | D4.2 Stakeholder Event 准备 + D4.1 交付 |

## 六、合同框架建议

我们建议分包合同明确以下边界：

- **包含**：T4.1 Pathfinder V1 软件 + 源代码 + Docker 部署包 + D4.1 Demo 支持 + D4.2 Event 技术支持
- **排除**（T4.3 V2 开发另签合同）：D4.3/D4.4 报告撰写（CHARITE 责任）、WP5/6/7 集成开发、生产运维、多语言、用户培训
- **返工**：因 WP2/3/8 上游数据格式变更、EHDS 实施细则中途颁布、Epidata 需求变更（超出签字原型）导致的返工，按人天另计

以上是我们的初步分析。期待与您进一步讨论，尽快敲定方向。

祝好，
峰哥
DataWego

附件：
- SCAILED WP4 九龙议会终论决议: ~/projects/scailed_wp4/council_debate_20260513/00_council_resolution.md
- 扩展技术分析: ~/projects/scailed_wp4/council_debate_20260513/09_expanded_analysis.md
