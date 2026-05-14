# SCAILED WP4 Pathfinder — Guido van Rossum(CLA) 设计审计

**审计日期**: 2026-05-14

---

## 一、Pydantic 模型和 API 设计 — 核心资产完全缺失

三份文档没有任何Pydantic模型定义。SQL Schema有了，Python模块目录有了，但中间层——类型系统——不存在。

**API端点设计不够完整：**

当前规划只有3个路由文件，缺失关键端点：
- `GET /health` — Docker Compose健康检查必备
- `POST /admin/rules/reload` — 文档承诺"规则热加载"但无管理接口
- `GET /v1/questionnaires/{type}` — 前端第一步就需要
- `POST /v1/assessments/{id}/answers/batch` — 20道题是一次提交还是逐题？影响前端状态管理和审计粒度
- `GET /v1/assessments` — CHARITE审计所有会话时需分页参数

**错误响应模型缺失。** solver.py抛出NoFeasiblePositionError，异常类未定义，无对应FastAPI exception handler。所有API错误应返回统一ErrorResponse。

建议：core/models.py和api/schemas.py明确拆分——数据库模型用SQLAlchemy 2.0 DeclarativeBase，API层用Pydantic。

---

## 二、规则引擎设计 — "声明式 YAML → Python 规则类"太空

1. **无YAML Schema。** rules/pharma_rules.yaml长什么样子？谁来保证格式合法？需JSON Schema或Pydantic模型做静态校验。

2. **Condition DSL不完整。** 示例有`{"gte": 3}`和`["A","B"]`，但操作符清单：eq, ne, gt, lt, in, contains, regex, and, or, not？缺少DSL定义 = 接口契约留白。

3. **规则冲突检测缺失。** 两条规则对同一(state_type, node_id)触发但给矛盾建议怎么办？priority只是整数，无冲突消解策略。

4. **热加载实现机制未定义。** watchdog监听文件系统？SIGHUP信号？API触发？Docker Compose单容器中文件系统watch在volume mount下行为诡异。

5. **规则测试框架缺失。** 建议每个YAML规则文件配.test.yaml：
```yaml
- rule_id: "R-PHARMA-AI-001"
  given:
    answers: {q2.1: 4, q3.2: "A"}
  expect:
    action: "Establish DPO"
    triggered: true
```

6. **solver.py第289行constraint.evaluate(state)。** constraint是什么类型？Python对象？函数？Pydantic验证器？类型系统完全崩溃。

建议：core/下加rules/子包，含parser.py, validator.py, compiler.py, loader.py。把"YAML→Python"魔法变成显式、可测试、带类型注解的管道。

---

## 三、知识产权条款 — "核心引擎"是法律模糊炸弹

当前条款：
> "DataWego保留核心引擎代码著作权"
> "Epidata获得SCAILED项目范围内的永久使用许可"
> "Pathfinder System在SCAILED项目外的商业化需另议"

具体问题：

1. **"核心引擎"无技术边界。** 是pathfinder/core/目录？solver.py和compliance.py？含YAML规则文件？如果Epidata工程师给graph.py提PR修bug，版权归谁？

2. **"永久使用许可"范围模糊。** 许可含修改权吗？再许可权？分发权？Docker镜像里的代码许可怎么算？

3. **第三方依赖许可污染。** FastAPI(MIT), NetworkX(BSD), PostgreSQL(PostgreSQL License), Vue3(MIT)都没问题。如果未来加PyTorch或GPL库，"核心引擎著作权"变复杂。合同应要求所有依赖许可事先书面同意。

4. **"项目外商业化另议"排他性。** 暗示DataWego可卖给其他客户但Epidata不行。建议：双方在项目结束后12个月内有优先谈判权。

5. **缺少开源许可选择。** "核心引擎"不应以GPL/AGPL发布（传染性太强）。建议对SCAILED项目用Apache-2.0或MIT。

**建议**：合同附件加IP_BOUNDARY.md，逐文件列出版权归属。

---

## 四、代码覆盖率 ≥80% — 对核心引擎是侮辱

1. 80%对FastAPI路由层和前端粘合代码可接受。对solver.py图算法、compliance.py约束检查、recommend.py路径映射——应≥95%，分支覆盖接近100%。

2. 无覆盖类型区分。建议合同明确：
   - 整体行覆盖率 ≥80%
   - core/目录分支覆盖率 ≥95%
   - solver.py和compliance.py行覆盖率100%

3. 覆盖率可被游戏化——test_foo(): assert True刷覆盖率。合同应要求mutation testing验证。

4. 缺性能测试量化。后端locate()方法是O(n)遍历所有节点，高并发出问题。验收标准应有p95延迟指标。

建议：拆成"外壳80%，内核98%"。加test_performance.py用pytest-benchmark。

---

## 五、Python 模块结构 — 至少缺6个关键目录

当前结构问题：
- frontend/不应在Python package内，移到repo根目录
- Dockerfile/docker-compose.yml应在repo根目录或deploy/
- tests/平铺太浅

**缺少的模块：**

1. **migrations/**（Alembic）— PostgreSQL JSONB，Schema冻结后可能微调。无Alembic = 手工ALTER TABLE。

2. **config/ 或 settings.py**（Pydantic Settings）— SECRET_TOKENS直接os.environ.get()太粗糙。

3. **exceptions/** — PathfinderError → NoFeasiblePositionError, ComplianceViolationError, RuleSyntaxError。这些异常分散在各文件或根本不存在。

4. **services/ 或 usecases/** — 路由→core间缺业务逻辑层。当assessments.py需"创建会话+校验问卷+生成初始推荐"时，orchestration代码放路由污染API层，放core/污染引擎层。

5. **scripts/** — 数据导入脚本、规则校验脚本、数据库备份脚本。

6. **tests/fixtures/** 和 **tests/conftest.py** — mock数据共享。

其他问题：
- 无.env.example
- 无Makefile或taskipy脚本
- api/routes/缺questionnaires.py

---

## 六、措辞过度承诺风险

邮件草稿危险措辞：

1. "带合规约束的战略定位与导航系统" — 决议明明说"带约束的图搜索引擎+问卷界面"。给甲方的邮件升级成"战略定位与导航系统"。

2. "不是黑箱AI" — 否定式营销让注意力停留在"AI"上。赵总可能回"那能不能加ChatGPT功能？"

3. "每条建议可审计追溯" — 仅靠PostgreSQL RULE实现的audit_log，不是区块链级不可篡改。

4. "类似于Apple Setup Assistant体验" — Apple有数百万美元UX研究。暗示这种体验 = 隐形金手铐。

SQL Schema技术漏洞：
- roadmap_nodes.parent_node是TEXT无REFERENCES外键
- recommendation_rules.node_id外键引用但主键是id SERIAL
- audit_log不可篡改性靠RULE是纸糊的
- assessment_sessions.answers JSONB无版本校验

---

## 总结：三条必须立即修补的红线

| 优先级 | 问题 | 建议动作 |
|--------|------|----------|
| 🔴 | Pydantic 模型完全缺失 | 在core/models.py和api/schemas.py补全所有类型定义 |
| 🔴 | "核心引擎著作权"边界模糊 | 合同附件加IP_BOUNDARY.md，逐文件列出版权归属 |
| 🔴 | 规则引擎DSL未定义 | 写rules/SCHEMA.json定义condition操作符全集 |
| 🟡 | 覆盖率80%不分层 | 拆成"外壳80%，内核98%"，加性能测试 |
| 🟡 | 模块结构缺migrations/config/exceptions | 补全目录结构，前端移出Python package |
| 🟡 | 邮件措辞过度承诺 | "战略定位"改回"图搜索引擎"，"Apple"类比删除 |

代码是写给人看的，碰巧能在机器上运行。目前三份文档里机器还没法运行任何东西——因为Pydantic模型不存在，异常类不存在，规则DSL不存在。建议在发给陆钊之前先把09_expanded_analysis.md的技术实现部分补成可pytest通过的骨架项目。
