# SCAILED WP4 — 数据 Schema 分析与应对方案

**日期**: 2026-05-19
**Branch**: feature/1000-mock-records
**议题**: Mock 数据 schema 与真实协作方数据的差异风险分析

---

## 一、三个 WP 的数据 Schema

### WP2 — 利益相关者分类

```json
{
  "stakeholder_type": "pharma-sme-001",
  "description":      "...",
  "capabilities":     ["legal-basis", "data-catalog", "secure-processing"],
  "pain_points":      ["limited_regulatory_expertise"]
}
```

| Key | 类型 | 含义 |
|-----|------|------|
| `stakeholder_type` | string | 唯一标识。`{类别}-{编号}` |
| `description` | string | 人类可读描述 |
| `capabilities` | list[enum] | 已有能力 (8个枚举值) |
| `pain_points` | list[enum] | 合规痛点 (6个枚举值) |

### WP3 — 合规路线图 DAG

```json
// Node
{
  "node_id": "n0000", "label": "...", "description": "...",
  "dimension": "data", "maturity_level": 1,
  "stakeholder_types": ["health-data-infrastructure"],
  "prerequisites": []
}
// Edge
{
  "edge_id": "e0000", "from_node_id": "n0000",
  "to_node_id": "n0105", "relation_type": "prerequisite"
}
```

| Key | 含义 |
|-----|------|
| `node_id` | 唯一标识 |
| `dimension` | governance / data / compliance / infrastructure / security |
| `maturity_level` | 1-10，图的 X 轴（层级） |
| `stakeholder_types` | 适用方列表，"all"=全部 |
| `prerequisites` | 前置节点列表，空=入口 |

### WP8 — 评估规则

```json
{
  "rule_id": "WP8-RULE-0001", "rule_type": "preference",
  "priority": 87, "applies_to": ["research-infrastructure"],
  "condition": {"field": "missing_capabilities", "operator": "contains", "value": "data-quality-kpi"},
  "action": {"title": "...", "text": "...", "node_id": "n0305"},
  "compliance_refs": ["MDR-Annex-I", "DGA-Art.7"]
}
```

| Key | 含义 |
|-----|------|
| `rule_type` | eligibility / exclusion / preference / override |
| `condition` | `{field, operator, value}` 或 `{and/or: [...]}` 嵌套 |
| `action.node_id` | **WP8→WP3 的桥** — 触发的规则路由到哪个路线图节点 |
| `compliance_refs` | 法规引用 |

---

## 二、三者关联

```
WP2.stakeholder_type ──匹配──→ WP8.rule.applies_to
                                       │
                                  WP8.rule.condition 匹配用户 answers?
                                       │
                                  WP8.rule.action.node_id ──指向──→ WP3.node.node_id
```

WP2 定义"谁在问"，WP8 定义"查什么"，WP3 定义"走到哪"。

---

## 三、当前代码中的硬编码点

### 路径 A: Mock REST (UpstreamClient)

```python
# upstream.py — 字段名硬编码
RoadmapNode(node_id=n["node_id"], label=n["label"], ...)
# ← 真实数据叫 "id" 不是 "node_id" → KeyError

# assessment_service.py
stakeholder_types = [s["stakeholder_type"] for s in client.stakeholders]
# ← 真实数据叫 "type" → KeyError
```

### 路径 B: Admin Import

```python
# import_wp3 — 严格 validation, 会抛明确的 ValueError
self._required_string(raw, "node_id")  # 缺失 → 立即报错
self._required_list(raw, "stakeholder_types")
```

---

## 四、断裂点矩阵

| Schema 变化 | Mock REST | Admin Import | 真实 REST |
|------------|:---------:|:------------:|:---------:|
| 字段改名 (`node_id`→`id`) | ❌ KeyError | ❌ ValueError | ❌ 同 Mock |
| 新增字段 | ✅ 忽略 | ✅ 忽略 | ✅ |
| 缺失字段 | ❌ KeyError | ❌ ValueError | ❌ |
| 类型变化 | ⚠️ 可能静默 | ❌ isinstance | ⚠️ |
| rule condition 新 operator | ❌ | ❌ | ❌ |
| 嵌套结构变化 | ❌ | ❌ | ❌ |

---

## 五、修复路径

适配层 (Guido pattern):

```python
# 上游数据 → normalize → 领域模型
def _normalize_node(raw: dict) -> dict:
    return {
        "node_id":   raw.get("node_id") or raw.get("id"),
        "label":     raw.get("label") or raw.get("title"),
        "dimension": raw.get("dimension", "governance"),
        ...
    }
```

**改动范围**: 仅 `pathfinder/adapters/upstream.py` 一个文件
**安全网**: `import_wp*` 的 validation 会在 normalize 之后二次检查

---

## 六、真实场景最可能差异

| WP | Mock 字段 | 真实可能叫 | 置信度 |
|----|----------|-----------|--------|
| WP2 | `stakeholder_type` | `id` + `label` + `personas` | 高 — import_wp2 已按此结构写 |
| WP3 | `node_id` | `id` | 中 |
| WP3 | `maturity_level` | `level` | 低 |
| WP3 | `stakeholder_types` | `applicable_to` | 中 |
| WP8 | `condition` | 嵌套 `and`/`or` 更深 | 高 |
| WP8 | `compliance_refs` | 拆成 `law`+`article`+`paragraph` | 中 |
