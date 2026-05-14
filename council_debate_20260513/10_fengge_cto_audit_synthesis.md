# SCAILED WP4 Pathfinder System — 六席联合审计终审报告

**终审人**: Feng Ge / CTO
**审计日期**: 2026-05-14
**审计范围**: 00_council_resolution.md + 09_expanded_analysis.md + email_to_lu_zhao_v1.md
**参审席位**: Xuefeng(CSA) / Musk(CVO) / Jobs(CPO) / Linus(Arch) / Guido(CLA) / Dijkstra(CSO)

---

## 综合风险矩阵（六席交叉验证）

| 风险编号 | 风险描述 | 提出席位 | 严重程度 | 达成共识 |
|----------|----------|----------|----------|----------|
| R1 | EU4Health IP规则：核心引擎著作权归DataWego违规 | Xuefeng, Guido | 🔴致命 | ✅ 双席确认 |
| R2 | EUR-X/天留空 + 返工条款缺审批流程和上限 | Xuefeng | 🔴致命 | ✅ 明确 |
| R3 | NetworkX+JSONB图计算性能在200+节点时崩溃 | Linus | 🔴致命 | ✅ 明确 |
| R4 | M9付款绑定CHARITE收款节点导致现金流断裂风险 | Xuefeng | 🔴致命 | ✅ 明确 |
| R5 | WP3结构化数据依赖无Plan B | Musk, Jobs | 🔴致命 | ✅ 双席确认 |
| R6 | Schema冻结无自动延期机制 | Xuefeng | 🔴极高 | ✅ 明确 |
| R7 | audit_log用PostgreSQL RULE不可靠 | Linus, Guido | 🟠高 | ✅ 双席确认 |
| R8 | recommendation_rules缺树结构(parent_rule_id) | Linus | 🟠高 | ✅ 明确 |
| R9 | Pydantic模型/异常类/规则DSL完全缺失 | Guido | 🟠高 | ✅ 明确 |
| R10 | 邮件措辞：Apple类比 + 导航过度承诺 + SHAIPED政治雷 | Jobs, Musk, Guido, Xuefeng | 🟠高 | ✅ 四席确认 |
| R11 | 36个月时间表患帕金森症，MVP可压缩至3-4月 | Musk | 🟡重要 | ⚠️ 单席 |
| R12 | "不是AI"定位防御性过强 | Musk | 🟡重要 | ⚠️ 单席 |
| R13 | 低保真原型不足以锁定QA文化需求 | Xuefeng, Jobs | 🟡重要 | ✅ 双席确认 |
| R14 | 缺用户故事/Demo/灵魂 | Jobs | 🟡重要 | ⚠️ 单席 |
| R15 | 验收标准缺乏测试条件约定 | Xuefeng | 🟡重要 | ✅ 明确 |
| R16 | FastAPI事件循环阻塞风险 | Linus | 🟡重要 | ⚠️ 单席 |
| R17 | 模块结构缺migrations/config/exceptions 6个目录 | Guido | 🟡重要 | ⚠️ 单席 |

---

## 峰哥战略裁决

### 第一优先级：必须在邮件发出前修正（否则等同自爆）

**1. IP条款重写（R1）**
Xuefeng和Guido一致判定：EU4Health的Foreground IP默认归项目联盟共有。
"DataWego保留核心引擎著作权"在法律上不可行。
→ 改为Background/Foreground分界模式，附IP_BOUNDARY.md附件逐文件列出版权归属。

**2. 返工条款补全（R2）**
EUR-X/天空白是法务审计炸弹。
→ 三档费率（架构师/高级/初级），加审批流程：书面提出→评估人天→双方确认→开始返工，设上限（单次≤15%，全年≤30%）。

**3. 图计算架构修正（R3）**
Linus一针见血：NetworkX纯Python实现在200+节点时会炸掉3秒SLA。
→ M4-M9引入Apache AGE（PostgreSQL原生图扩展），Docker Compose无需额外容器。

**4. 付款结构加固（R4）**
Xuefeng算了一笔账：30%预付刚好够9个月工资，M9款绑定CHARITE = 断粮。
→ 拆分M9付款为两笔（M9 15% + M15 15%），或加CHARITE拖款超30天Epidata先行垫付条款。

**5. WP3数据Plan B（R5）**
Musk和Jobs都指出：你的方案在WP3交PDF时没有Plan B——这不是架构问题，这是生存问题。
→ 增加数据提取层（即使人工策展），合同要求Epidata保证结构化交付或出资提取。

### 第二优先级：在合同谈判前必须完成

**6. Schema延期机制（R6）**
M3签不下来时自动延至M5，付款节点顺延。加条款："上游M3后改Schema → 返工按费率计费"。

**7. 审计日志加固（R7）**
PostgreSQL RULE → TRIGGER。Linus和Guido双重判定RULE不可靠。加分：prev_hash加密链式哈希。

**8. 规则引擎重构（R8）**
recommendation_rules加parent_rule_id + priority + rule_type枚举。WP8规则是树不是列表。

**9. 代码骨架先行（R9）**
Guido说得对：三份文档里没有任何一个Pydantic模型、异常类、规则DSL。在发邮件前补一个可pytest的骨架项目。

### 第三优先级：邮件措辞政治修正

**10. 措辞四连杀（R10）**
四席交叉确认为政治风险：
- "Apple Setup Assistant" → "简洁三步引导体验"（Jobs判定QA文化不吃这套）
- "战略定位与导航系统" → "合规路径映射工具"（Musk: 导航=过度承诺）
- SHAIPED"哪些可以复用哪些建议重写" → "与SHAIPED架构对齐，为SCAILED场景扩展"（Jobs: 别在前女友面前说坏话）
- "Schema必须在M3签字" → "双方M3前共同确认Schema基线"（Xuefeng: 对抗改成合作）

---

## 终审裁决

计划骨架正确、方向正。但六席审计暴露了三大类12个致命/极高风险。**邮件当前版本不可发送。**

行动清单：
1. 🔴 重写IP条款（Background/Foreground分界 + IP_BOUNDARY.md）
2. 🔴 补全返工条款（三档费率 + 审批流程 + 上限）
3. 🔴 图计算方案修正（引入Apache AGE替代纯NetworkX）
4. 🔴 付款结构拆分（M9分两笔或加垫付条款）
5. 🔴 增加WP3数据Plan B（提取层 + 合同约束）
6. 🔴 Schema自动延期 + 上游变更计费条款
7. 🟠 审计日志RULE→TRIGGER + 加密链哈希
8. 🟠 recommendation_rules加树结构
9. 🟠 搭建可pytest的代码骨架（Pydantic + exceptions + DSL）
10. 🟠 邮件措辞重写（4处修正）

最后一刀：邮件结尾加一句灵魂——"Pathfinder不是帮你填合规表格。它让合规变成直觉。"
