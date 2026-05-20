# 议会辩论记录 — Schema Drift 应对方案

**日期**: 2026-05-20
**议题**: Mock 数据 schema 与真实协作方数据的差异风险分析及应对方案
**辩论子集**: Architecture + Audit (Guido/Linus/Dijkstra/雪峰/Musk)
**决议**: 5/5 全票通过 — 立即在 upstream.py 加入 version-aware normalize 层

---

## 一、背景

SCAILED WP4 Pathfinder 依赖三个上游 Work Package 的数据: WP2(利益相关者分类), WP3(合规路线图 DAG), WP8(评估规则)。当前 mock 数据字段名是假设的——真实协作方 (CHARITE, Epidata, 法律团队) 交付的真实数据 schema 大概率不同。

断裂点矩阵: 字段改名 → KeyError, 类型变化 → 静默/崩溃, 嵌套结构变化 → ValueError。修复半径: 一个文件 (`pathfinder/adapters/upstream.py`)。

---

## 二、各席位发言

### 1. 张雪峰 (CSA, deepseek-v4-flash, 25s) — 成本审计

> "0.5人天就能把'M3 demo当场崩掉'的风险从70%降到10%以下，这账不算我张雪峰白干这行了。但别现在做架构——你连对方面孔都没见过，就急着给人盖房子，盖出来也是拆。"

| 维度 | 方案A（等） | 方案B（大干） | 方案C（推荐） |
|------|-----------|------------|------------|
| 现在花多少钱 | €0 | €1,160-1,740 | €175 |
| M3失败概率 | 高（70%+） | 中 | 低 |
| M3改造成本 | 紧急2-3天 | 重构1-2天 | 改YAML 10分钟 |
| 过度工程风险 | 无 | 高 | 极低 |
| ROI | 负 | 负 | 极高 |

> "YAML 配置驱动的字段翻译 + Graceful Degradation = €175买份保险。不做就是赌M3的数据跟mock一样。我赌过太多场了，这种赌局十赌九输。"

### 2. Linus Torvalds (Arch, deepseek-v4-pro, 60s) — 架构判决

> "You identified failure modes. You have the file. You have a developer. Why the hell would you wait for the crisis?"

架构方案: version-aware `_FIELD_MAP` dict + normalize function:

```python
_FIELD_MAP = {
    "1.0": {"node_id": "node_id", "stakeholder_type": "stakeholder_type"},
    "charite_v1": {"id": "node_id", "type": "stakeholder_type"},
}

def _normalize(record: dict, schema_version: str) -> dict:
    mapping = _FIELD_MAP.get(schema_version, _FIELD_MAP["1.0"])
    return {mapping.get(k, k): v for k, v in record.items()}
```

> "One file, one normalize function, one validation gate, version-aware mapping table. Do it now."

### 3. Guido van Rossum (CLA, kimi-2.6, 104s) — API 设计

> "Fix the adapter now. €145K buys us the discipline to front-load this pain."

方案: version dispatch hook + per-WP normalizer functions:

```python
_WP2_NORMALIZERS = {"v1": _normalize_wp2_v1, "v2": _normalize_wp2_v2}

def get_wp2_normalizer(schema_version: str | None) -> Callable:
    version = schema_version or "v1"
    if version not in _WP2_NORMALIZERS:
        raise ValueError(f"Unsupported WP2 schema version: {version!r}")
    return _WP2_NORMALIZERS[version]
```

> "Simple is better than complex. The mapping table is almost embarrassingly simple — which means it will survive contact with the enemy."

### 4. Elon Musk (CVO, kimi-2.6, 80s) — 第一性原理

> "€2K decision prevents €500K M3 firefight."

核心方案: 一个 versioned envelope `{version, schema, payload}` → transform → canonical model。删掉重复 validation，删掉 schema 协商流程。

> "Cardinality is not an interface constraint. 6 nodes. 6,000 nodes. Zero nodes. The adapter doesn't care about cardinality. It cares about structure."

> "This is how SpaceX builds rockets: question the requirement, delete the process, simplify to physics, then accelerate."

### 5. Edsger Dijkstra (CSO, kimi-2.6, 99s) — 形式化验证

> "A 20-line explicit mapping table with exhaustive else: raise beats a 200-line 'flexible' reflection-based normalizer every time."

四个不变量:
1. **I1 (Completeness)**: normalize 输出必须包含所有下游模块需要的字段
2. **I2 (Identity)**: 对已规范的字段, normalize(normalize(x)) = normalize(x)
3. **I3 (Surjectivity)**: normalize 的值域 = 领域模型字段的笛卡尔积
4. **I4 (No silent failure)**: 输入字段不在 mapping domain 中 → 报警

> "Define the mapping M explicitly as a bijection from expected input variants to canonical fields. Any field not in M's domain must trigger an alert."

---

## 三、计票

| 席位 | 现在修 | 方案 | 估时 |
|------|:-----:|------|------|
| 雪峰 | ✅ | YAML config-driven + graceful fallback | 0.3d |
| Linus | ✅ | _FIELD_MAP dict + normalize function | 2d |
| Guido | ✅ | Version dispatch hook + per-WP normalizer | 1d |
| Musk | ✅ | Versioned envelope → canonical model | 1d |
| Dijkstra | ✅ | Total function + 4 invariants | 1d |
| **CTO** | **✅** | **Synthesis** | **1d** |

**票数: 5/5 全票通过, 现在就修**

---

## 四、议会决议

> **立即在 `pathfinder/adapters/upstream.py` 加入 version-aware normalize 层。改动范围: 一个文件。估时: 1 人天。**

**实现内容**:
1. `_NORMALIZERS: dict[str, callable]` — 每个已知 schema 版本一个映射函数
2. `normalize(raw: dict, version: str) → dict` — 字段名翻译到 canonical model
3. 未知版本 → `ValueError` + log
4. 未知字段 → log warning, 不崩溃
5. 节点数量不限 (Dijkstra: cardinality is separate concern)
6. 不重复 validation (import_wp* 已有, Musk: delete the second one)

**为什么不等 M3**:
- 现在: €175-€580 (1人天)
- 等到 M3: 紧急修 2-3天 + demo 崩掉的信用损失
- Musk: "€2K decision prevents €500K firefight"
- 雪峰: "M3失败概率从70%降到10%以下"

---

**归档**: docs/records/2026-05-20-council-debate-schema-drift.md
**签署**: 峰哥 (CTO, 议会召集人)
**日期**: 2026-05-20, The Hague
