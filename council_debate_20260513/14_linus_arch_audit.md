# SCAILED WP4 Pathfinder — Linus Torvalds(Arch) 架构审计

**审计日期**: 2026-05-14

---

## 1. Python 3.12 + FastAPI + NetworkX + PostgreSQL JSONB — 技术栈隐患

**NetworkX是大问题。**

NetworkX是纯Python实现的图算法库。底层数据结构是Python dict-of-dicts。每次节点访问都是Python对象解引用。

- 100节点、几百条边：NetworkX没问题，~50ms
- 1000节点、上万条边（EHDS合规场景极容易达到）：NetworkX把3秒SLA炸成30秒
- 10,000节点、50,000边：shortest_path需200-500ms仅算路径，加WP8规则约束（动态过滤边）每次查询重建子图，翻倍

**PostgreSQL JSONB存图是架构层面的错误选择。**

JSONB是文档存储。当图数据库用 = 螺丝刀敲钉子——能敲进去但毁掉墙。

拒绝Neo4j没问题（资源消耗大、查询语言特殊）。但PostgreSQL有Apache AGE（PG原生图扩展，兼容openCypher）。AGE把图操作下推到C层，性能是NetworkX的50-100倍。或者pgRouting——也是PG扩展。

| 场景 | JSONB + NetworkX | PostgreSQL AGE | 纯Neo4j |
|------|-----------------|----------------|----------|
| 50节点, 200边 | ~50ms | ~1ms | ~2ms |
| 200节点, 1000边 | ~300ms | ~5ms | ~8ms |
| 500节点, 3000边 | ~2s | ~15ms | ~20ms |
| 1000节点, 8000边 | ~8s | ~40ms | ~50ms |

NetworkX曲线是指数的——因约束剪枝在Python层遍历节点。

SLA前端≤3秒。500节点NetworkX吃掉2秒。WP8规则多时100节点就能突破3秒。

**建议：M4-M9核心引擎阶段引入Apache AGE。** PG扩展，不额外容器，Cypher直接嵌入SQL。

**FastAPI + Pydantic v2没问题。** 但隐患：NetworkX纯同步，Solver.solve()跑2秒会阻塞FastAPI事件循环。需ThreadPoolExecutor包装。

---

## 2. Solver类代码审计

必须有的异常处理：

1. **DisconnectedGraphError** — WP8规则过滤后用户节点到目标间无路径，返回明确错误而非空列表
2. **CycleDetection** — 合规图如果有环，DFS无限递归
3. **TimeoutGuard** — 约束组合导致搜索空间爆炸（NP-hard），N秒后返回"partial results + timeout warning"
4. **EmptyRuleSet** — WP8规则集为空时回退行为需定义
5. **ConstraintConflictError** — 两条WP8规则矛盾时明确报错，非静默返回

代码结构：单体Solver类拆成GraphLoader + ConstraintEvaluator + PathFinder。

---

## 3. 单体Docker Compose部署

T4.2 Test Drive勉强够（2-3内部用户）。单容器无水平扩展。

模糊点：Docker Compose是"单容器"还是"单服务"？如果PostgreSQL同容器打包——灾难。数据库需独立持久化volume。

Epidata是CHARITE合作伙伴（德国最大大学医院之一），习惯企业级软件。交给他们`docker-compose up -d`，法务部门会问："灾备方案在哪？高可用在哪？"

**建议**：交付文档明确写V1是单机部署模式。想要K8s是V2的事。

---

## 4. 审计日志的PostgreSQL RULE方案

**PostgreSQL RULE是错的，直接改。**

PG官方文档："The rule system is more complex and less efficient than the trigger system in most cases." RULE系统有反直觉行为——RETURNING子句异常，COPY绕过RULE。

改用**ROW LEVEL SECURITY + BEFORE UPDATE/DELETE TRIGGER**：

```sql
CREATE FUNCTION audit_log_no_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only. UPDATE/DELETE rejected.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_append_only
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_no_mutation();
```

另外：**audit_log缺cryptographic_chain_hash。** 每行存prev_hash（SHA-256）。任何人篡改中间某行，后续所有哈希断裂。EU GDPR审计员会检查。

---

## 5. JSONB存图 vs 图数据库

拒绝Neo4j讲得通。用PostgreSQL完全行。但应使用Apache AGE或pgRouting，而非JSONB+NetworkX。

建议M4-M9就迁到AGE。Cypher查询直接嵌入SQL：

```sql
SELECT * FROM cypher('roadmap_graph', $$
    MATCH (start:Node {id: 'A'})-[*]->(end:Node {id: 'B'})
    RETURN end
$$) AS (result agtype);
```

现状JSONB+NetworkX在200+节点时会炸。

---

## 6. 数据Schema遗漏

**缺的表：**
1. **schema_versions** — 记录每次Schema变更的版本号、变更人、变更原因、生效时间
2. **rule_versions** — WP8规则修订版追踪，需要生效时间段
3. **upstream_data_snapshots** — 记录每次从WP2/WP3/WP8拉取数据的时间戳和校验和

**缺的字段：**
- assessment_sessions缺client_ip_hash（GDPR审计要求）
- audit_log缺prev_hash（加密链式哈希）
- assessment_sessions缺schema_version_id（评估时用的Schema版本）

**recommendation_rules表设计根本上错了。**

WP8规则是决策树，平面表存树结构需parent_rule_id字段：

```sql
recommendation_rules (
    id UUID PRIMARY KEY,
    version_id UUID REFERENCES rule_versions(id),
    parent_rule_id UUID REFERENCES recommendation_rules(id),
    rule_type ENUM('eligibility', 'exclusion', 'preference', 'override'),
    condition JSONB,
    priority INTEGER,
    action JSONB,
    effective_from TIMESTAMPTZ,
    effective_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**缺API速率限制。** 恶意客户端一分钟打10000次POST /assessments。

---

## 总结

| # | 问题 | 严重级别 | 建议 |
|---|------|---------|------|
| 1 | NetworkX + JSONB 图计算性能 | CRITICAL | M4-M9 引入 Apache AGE |
| 2 | FastAPI 事件循环阻塞 | HIGH | ThreadPoolExecutor 包装 solver |
| 3 | PostgreSQL RULE 做审计 | HIGH | 改为 TRIGGER |
| 4 | audit_log 无加密链 | MEDIUM | 加 prev_hash 字段 |
| 5 | 缺表 (schema_versions, rule_versions, snapshots) | MEDIUM | 在 Schema 冻结前补上 |
| 6 | recommendation_rules 缺少树结构 | HIGH | 加 parent_rule_id + priority |
| 7 | 无 API 速率限制 | LOW | FastAPI 加 throttling 中间件 |
| 8 | 单容器部署预期管理 | LOW | 明确写在交付文档里 |

技术方向大体正确，但图计算选型是定时炸弹。Talk is cheap. Fix the graph engine.
