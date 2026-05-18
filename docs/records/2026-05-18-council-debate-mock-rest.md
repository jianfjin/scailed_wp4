# 议会辩论记录 — Mock REST vs JSON 文件方案

**日期**: 2026-05-18  
**议题**: Phase 0 是否构建 Mock REST 容器模拟上游 WP 服务  
**决议**: 6:1:1 反对 Mock REST → 7:0 通过 JSON 文件方案 → **陛下行使一票否决权**  
**最终**: 坚持 Mock REST 方向，创建 feature/mock-upstream-rest-services 分支

---

## 一、议会辩论 (Inner Circle Debate)

### 核心分歧

**A 方案 — Mock REST 容器** (陛下主张)  
构建 wp2-mock, wp3-mock, wp8-mock 三个独立容器，用 aiohttp.web 提供 REST API。  
Pathfinder Backend 通过 aiohttp.ClientSession 异步获取数据。  
估时: 4.5人天。Docker Compose 从 5 容器增至 8 容器。

**B 方案 — JSON 文件加载** (议会多数主张)  
在 fixtures/demo/ 目录下放置版本化的 JSON 文件。  
Pathfinder Backend 启动时用 `json.loads(file.read())` 加载。  
估时: 1人天。不增加任何容器。

---

### 各席位发言 (按发言顺序)

#### 1. Linus Torvalds (Arch, pro) — 反对 Mock REST

> "我们刚修了 4 个 middleware bug。现有的 5 个容器还没跑稳，你就要加 3 个新的？  
> Bug A 是 `/health` 路径匹配问题，Bug C 是空 token 在生产环境直接炸。  
> 这些是实打实的生产级 bug。先把手上的代码跑稳，再加复杂度。  
> JSON 文件方案 1 人天就能出活，mock 容器要 4.5 人天 —— 差出来的 3.5 天够我再审计一轮 security gate 了。"

**立场**: 反对 Mock REST。优先修 bug，不引入新复杂度。

---

#### 2. Guido van Rossum (CLA, k2.6) — 反对 Mock REST

> "核心原则: **separate loader from transport**。  
> `import_wp3(data: bytes)` 不关心数据是从文件读的还是从网络来的。  
> 你用一个函数签名把 loader 和 transport 解耦，将来切到真实 API 只需要换一个调用方。  
> 现在写 mock REST 容器，本质上是提前把 transport 层做了。  
> 这是 premature implementation。写三个 aiohttp 服务来模拟一个迟早要替换的东西 ——  
> 不是在写测试，是在写 throwaway code 但用 production 标准。"

**立场**: 反对 Mock REST。Loader/Transport 分离是正确架构，JSON 文件是最简 Loader。

---

#### 3. Dijkstra (CSO, k2.6) — 反对 Mock REST

> "合规系统的核心需求是确定性和可审计性。  
> 同一个输入必须永远给出同一个合规评估结果。  
> 网络是 non-deterministic。mock 容器虽然可控，但它引入了 HTTP 往返、  
> 连接超时、重试策略等变量。这些变量在没有 mock 容器时根本不存在。  
> JSON 文件是 immutable snapshot。git 版本号就是 audit trail。  
> 五年后有人问 '你们 2026 年的合规评估是基于什么数据做的'——  
> 我给他一个 git commit hash 就完了。网络请求？你解释不清楚。"

**立场**: 反对 Mock REST。Immutable snapshots 是合规系统的基石。JSON 文件 = git-tracked audit trail。

---

#### 4. 张小龙 (Eng, pro) — 弃权

> "从工程角度看，两个方案技术上都没问题。  
> JSON 文件更简单，mock 容器更接近生产拓扑。  
> 但我担心 mock 容器的维护成本。WP2/WP3/WP8 的 API contract 一旦变更，  
> mock 容器要同步更新，JSON fixtures 也要同步更新 —— 维护两份。  
> 如果议会认为这不是问题，我没意见。这一票我弃权。"

**立场**: 弃权。技术上均可，担心双份维护成本。

---

#### 5. Jobs (CPO, k2.6) — 反对 Mock REST

> "我们的预算 145K 欧元，一个人干。项目交付物是 D4.1 demo。  
> D4.1 的要求是展示 CSP path engine 能跑 —— 不是展示你会写 REST API。  
> JSON 方案: 90% 价值，10% 工作量，0 新容器。  
> Mock REST 方案: 100% 价值模拟，但多了 3 个要维护的容器。  
> 这是典型的 over-engineering for a demo。D4.1 不需要 REST 级别的模拟。  
> 到 Phase 1 协作方真给 API 的时候再切不迟。"

**立场**: 反对 Mock REST。Demo 阶段，JSON 方案性价比最高。

---

#### 6. Musk (CVO, k2.6) — 反对 Mock REST

> "我关注的是速度。我们需要在 M3 之前确认 V1 scope、stakeholder types、  
> data contracts。这些是外部依赖，不是我们能控制的。  
> 每花一天在 mock 容器上，就少一天去做和 Epidata/CHARITE 的 scope alignment。  
> JSON 文件 1 天出活，剩下的 3.5 天拿去做 stakeholder review。  
> 这是资源分配问题，不是技术问题。"

**立场**: 反对 Mock REST。资源应优先投入外部依赖确认 (scope alignment)。

---

#### 7. 张雪峰 (CSA, flash) — 反对 Mock REST

> "峰哥，我说句扎心的。Mock REST 在 Phase 0 做，属于典型的'自己想爽一把'。  
> 技术上没毛病，时间上不对。D4.1 验收方不看你有没有 REST 容器，  
> 看你 graph engine 能不能跑出合规路径。  
> JSON 方案 1 天干完，剩下时间我们还能把 demo rules 从 15 条扩到 25 条。  
> 这才是验收方真正想看的东西。"

**立场**: 反对 Mock REST。D4.1 验收标准是 Graph Engine 功能，非容器拓扑。

---

#### 8. Jensen (CIO, flash) — 未投票 (技术顾问发言)

> "我说个运维视角的建议。如果最终要上 mock 容器，注意两件事:  
> 1. 统一 Dockerfile，不要三个容器三个 Dockerfile。  
> 2. 必须上 healthcheck，否则 backend 启动时连不上 mock 容器会挂。  
> 但从 Phase 0 的交付节奏看，我倾向 JSON 方案。"

**立场**: 技术建议 (JSON 优先)，正式投票中未计入。

---

### 计票

| 席位 | 姓名 | 投票 | 核心理由 |
|------|------|------|----------|
| Arch | Linus | ❌ Mock REST | Fix bugs first; don't add complexity |
| CLA | Guido | ❌ Mock REST | Separate loader from transport |
| CSO | Dijkstra | ❌ Mock REST | Immutable snapshots for audit trail |
| CPO | Jobs | ❌ Mock REST | 90% value, 10% work; over-engineering for demo |
| CVO | Musk | ❌ Mock REST | Resource allocation: prioritize scope alignment |
| CSA | 张雪峰 | ❌ Mock REST | D4.1 acceptance criteria is graph engine, not REST |
| Eng | 张小龙 | ⚪ 弃权 | Technically fine; worried about dual maintenance |
| CIO | Jensen | — 顾问发言 | 运维建议; 倾向 JSON |

**票数: 6 反对 Mock REST · 0 支持 · 1 弃权 · 1 顾问发言**

### 议会决议

> **议会以 6:1:1 否决 Mock REST 方向，以 7:0 通过 JSON 文件方案。**  
> Phase 0 采用 `fixtures/demo/*.json` + `json.loads()` 作为 Mock 数据策略。

---

## 二、陛下否决

### 否决声明 (2026-05-18, 当日)

> **"朕一票否决，坚持 mock REST 方向。现在就开一个新的 branch，专门做这个任务。"**

### 否决理由 (综合陛下历次言论)

1. **完整模拟生产拓扑** — JSON 文件能模拟数据但不能模拟服务拓扑。  
   8 容器的 Docker Compose 拓扑本身就是 D4.1 交付物的一部分。

2. **可验证的切换路径** — Mock REST → 真实 API 切换只需改环境变量，  
   代码零改动。这是系统设计层面的保证，不是"将来再改"的承诺。

3. **议会过度保守** — 6:1:1 的投票结果反映了议会"先修 bug 再加功能"的倾向，  
   但 Mock REST 不是"新功能"，是架构完整性的一部分。

4. **不允许 compromise on architecture** — JSON 方案是 pragmatic tradeoff，  
   但不是 right architecture。给协作方展示的是真实的 8 容器部署拓扑，  
   不是降级的文件加载方案。

---

## 三、议会回应与执行

### 峰哥 (CTO, 议会召集人) 回应

> "陛下否决合理。议会的 6:1 投票本质上是'时间 vs 架构'的 tradeoff — 我们选了 time，  
> 陛下选了 architecture。在 D4.1 交付压力下，议会的 pragmatic 判断没错；  
> 但从系统完整性和长期维护性看，陛下的方向更对。  
>   
> 立即执行: feature/mock-upstream-rest-services 分支，aiohttp 统一两端，4.5 人天。"

### 执行情况

| 事项 | 状态 |
|------|------|
| 分支创建 | ✅ feature/mock-upstream-rest-services |
| 实现方案 (MD) | ✅ docs/plans/2026-05-18-004-mock-upstream-rest-services.md |
| 架构图 (HTML) | ✅ docs/diagrams/2026-05-18-architecture-8-containers.html |
| 技术规格 (HTML) | ✅ docs/specs/2026-05-18-mock-upstream-rest-services.html |
| 议会辩论记录 | ✅ docs/records/2026-05-18-council-debate-mock-rest.md (本文档) |
| 代码实现 | ⏳ 待执行 |

---

## 四、附录: 议会章程相关条款

此否决触及议会章程第 7 条:

> **第 7 条 — 陛下保留权**  
> 议会有权提出、辩论、决议。决议对技术细节具有约束力。  
> 但陛下对以下事项保留一票否决权:  
> (a) 系统架构方向  
> (b) 对外交付物形态  
> (c) 资源分配优先级  
>   
> 本次否决属于 (a) 系统架构方向 —— Mock REST 容器属于架构完整性范畴。  
> 否决有效，议会无条件执行。

---

**归档**: docs/records/2026-05-18-council-debate-mock-rest.md  
**签署**: 峰哥 (CTO, 议会召集人) · 陛下 (SCAILED WP4 Project Owner)  
**日期**: 2026-05-18, The Hague
