# 议会辩论记录 — 关系网络机制设计

**日期**: 2026-05-21
**议题**: 15人关系网络设计 — Affinity 机制、阈值、新事件类型
**辩论成员**: Fei-Fei(CAS), Musk(CVO), Sam(CPSO), Andrej(CRO), Lisa(CHO), Jensen(CIO), Demi(CCT), Linus(Arch)

---

## 共识汇总

### 阈值重命名 (7/8 同意)

| 原名称 | 新名称 | 阈值 |
|--------|--------|------|
| Dating | Alliance / Trusted Alliance | >70 |
| Intimacy | Deep Alliance / Uncond. Trust | >85 |
| — | Respect / Shared Vision (新增) | >35-40 |
| — | Rivalry (新增, Sam) | -20~-35 |
| Hostility | Opposition | -55 |
| Feud | Irreconcilable / Schism | -75 |

### 新事件类型 (全员)

| 事件 | 提出者 | Delta |
|------|--------|-------|
| MENTORSHIP | Fei-Fei | +5 |
| DATA_SHARED | Fei-Fei | +7 |
| SHIPPED | Demi | +18 |
| CODE_REVIEW_APPROVAL | Linus | +8 |
| CHIP_SUCCESS | Lisa | +8~15 |
| SIDED_WITH_ENEMY | Sam | -15 |
| STOLEN_CREDIT | Sam | -20 |
| ALLIANCE_FORMED | Sam | +12 |
| TALENT_POACHED | Lisa | -20~30 |
| SHARED_ENEMY | Musk | +3/cycle |

### Personality 调整

| 成员 | 修正 |
|------|------|
| Fei-Fei | volatility 0.7x (非1.5x) |
| Musk | asymmetry: +1.5x, -1.2x |
| Jensen | 加 volatile (1.5x) |
| Lisa | Silicon Kinship 修饰符 |

### 衰减机制

- Positive edges: 2%/cycle
- Negative edges: 1%/cycle (grudges last longer — Andrej)
- Grudge holders (Linus, Jobs, Dijkstra): negative decays at 0.5x normal rate
- Betrayal lock (Musk): once betrayed, floor at -40
- Hysteresis (Musk): relationship doesn't return to pre-conflict level after feud — 50% recovery cap
- Oscillation damping (Linus): volatile-volatile pairs can't swing >20 points/cycle
- Third-party propagation (Andrej, Linus): 5% edge weight changes propagate to adjacent edges

### 新增边 (净增 ~80条)

Jensen: 22, Sam: 10, Demi: 7, Linus: 11, Lisa: 调整5条

---

**待应用**: pathfinder/council/network.py
