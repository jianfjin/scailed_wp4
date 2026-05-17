# SCAILED WP4 Pathfinder — 下一步任务议会决议

**日期**: 2026-05-17
**议会**: 5席 (Musk/Xiaolong/Linus/Jobs/Xuefeng + CTO Feng Ge)
**议题**: Phase 0 (M1-M3) 任务优先级排序

## 当前基线

| 指标 | 状态 |
|------|------|
| 代码实现 | pathfinder/core + api + services + adapters (约1700行) |
| 测试 | 13/13 pass (VM端8 + AGE接口5) |
| AGE连线 | 本地峰哥 (hermes-asus.datawego.nl) 验证跑通 |
| 部署 | deploy/docker-compose.yml + Dockerfile×3 就绪 |
| 文档 | architecture-spec.html §02a-f, council_resolution (8/8融合) |
| 邮件 | email_to_lu_zhao_v3.md (含CHARITE技术栈三问) |
| Pre-contract投入 | 约30人天 ≈ €21,000 (Xuefeng审计) |
| 资金 | €145K总预算, 预付30%=€43,500, M1-M3可用约32人天 |

## Mock数据

| 类型 | 当前数量 | D4.1需要 |
|------|---------|---------|
| Stakeholder types | 5 | 5 ✅ |
| 问卷问题 | 6 (3数值/2多选/1可选) | 够用 ✅ |
| Roadmap nodes | 6 | 够演示 ✅ |
| Roadmap edges | 6 | 够演示 ✅ |
| Rules | 3 | 3够演示核心逻辑, Phase 1扩展到15-20 |
| Rule tests | 1 paired test | 每条规则一个test ✅ |

## 5/5全票共识

1. **Rate limiting推到V2** — Nginx挡一下够用
2. **Alembic不需要** — pg-init SQL足够, V1 schema稳定后再说
3. **砍掉3.5 (e2e API flow)** — 与1.5+2.7重叠
4. **本地峰哥角色**: 70%后端+测试, 验证AGE可复现性

## CTO裁决 (分歧项)

| 议题 | 裁决 | 理由 |
|------|------|------|
| 前端交互式表单 | **做** (200行, 1天) | API已就绪, Linus估计1-2天 |
| 邮件发送时机 | **明天发** | e2e验证完后立即发v3 |
| Demo数据扩展 | **Phase 1做** | 当前3规则够演CSP核心 |

## M3前执行清单 (优先级排序)

```
P0  1. 1.5 e2e闭环验证
       import → questionnaire → assessment → recommendation → Docker boot
       录demo video, 这是M3硬通货

P1  2. 2.2 AGE runtime连线 (VM端)
       本地峰哥已验证, VM端补上

P2  3. 3.2 API schema锁定 + error model (3-5种错误码)
       前后端合约锁死

P3  4. 前端交互式表单
       替换hardcoded useMemo, 200-400行React, 1天

P4  5. 2.7 core tests + p95 latency (demo scale)
       D4.1需要数字: "p95 < Xms @ N条数据"

P5  6. 4.4 clean install验证
       干净环境从0装一遍, 补文档缺口

P6  7. 发送email_to_lu_zhao_v3
       附demo video链接 + Docker部署命令
```

## 推迟到Phase 1 (M4-M8)

- 4.1 文案打磨 (等stakeholder反馈)
- 4.3 Stakeholder review sessions (demo跑通后再review)
- 5.x V2 scoping + validation support
- Demo数据扩展 (8-10 stakeholders, 15-20 rules, 冲突场景)

## Xuefeng预算警告

M1-M3必须做14人天 (€9,800)。剩余约18人天缓冲。
任何突发需求会吃光缓冲。合同必须设15%/30%变更上限。

---

*存档: council_debate_20260513/17_next_steps_resolution.md*
