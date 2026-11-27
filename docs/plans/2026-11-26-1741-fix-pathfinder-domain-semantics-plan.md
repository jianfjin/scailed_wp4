---
title: "Pathfinder Domain Semantics - Plan"
type: fix
date: 2026-11-26
deepened: 2026-11-26
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# Pathfinder Domain Semantics - Plan

## Goal Capsule

- **Objective:** 用户能识别推荐的依据与不确定性，在输入被撤回后停止获得受影响的新建议，同时仍可追溯原始历史结果。
- **Means:** 在现有模块化单体中落实领域约束，沿用确定性核心与快照接入模式，见 KTD1。
- **Authority:** 产品行为以 R1–R12 和已确认的语义基线为准；KTD 决定实现机制，U-ID 不覆盖两者。共享协议的正式效力受 R10 的双边 RFC 约束。
- **Execution profile:** 一个 PR、八个依赖有序的实现单元；内部实现与合成数据验证可先完成，生产切换受 G1–G3 发布门槛约束。
- **Ownership:** 实施者负责实现、验证证据和交付文档；来源 WP 与受影响消费者确认协议；运维负责受控迁移。此计划不代替跨 WP 签署。
- **Stop conditions:** 若实现需要重释历史结果、扩大机构身份范围或绕过内容方确认，应停止该部分并回到其所属需求；缺少正式确认时不得宣称已完成生产切换。

---

## Product Contract

### Summary

定向修复 Pathfinder 的能力判断、条件求值和输入生命周期，使推荐与历史导出遵守已确认的领域含义。
范围包含必要的契约主版本迁移、会话证据绑定和展示一致性；保留当前架构。

### Problem Frame

`docs/domain-modeling/2026-11-26-pathfinder-semantic-baseline.md` 与 ADR 0004–0007 已明确参考信息、自报、核验、未知和撤回的区别。
当前布尔求值会丢失未知，旧 WP2 推导会产生本次能力与缺口，现有状态没有逐项证据性质。
快照代次与会话绑定提供了版本基础，但尚无撤回消费约束。

另外，`AssessmentService.submit_answers` 更新答案后仍可能保留旧推荐，报告再将它与新会话状态组合。
这直接影响证据追溯，需要与本次能力来源改造一起处理。

### Actors

- A1. 评估使用者：填写当前会话的回答，查看本次或指定历史结果。
- A2. 内容负责方：WP2 确认分类，WP3 确认路线图，WP8 确认规则，WP4 对其问卷内容负责。
- A3. 授权接入管理员：按已确认内容记录接收、激活和转交撤回，不取得上游内容解释权。
- A4. 消费者：服务 API、React 页面、HTML 报告与 FHIR 导出。

### Requirements

**Assessment evidence**

- R1. 无回答且无其他依据的能力判断保持未知，明确否定必须来自当前回答或可追溯依据。
- R2. 必要条件未知时输出条件性方向和待补信息，明确尚不能确认路径可执行；已知阻断与信息不足分别表达。
- R3. 每项能力判断保留来源和核验性质，自报可用于注明依据的推演，填写完整度不得升级为真实性核验。
- R4. WP2 类型能力只作分类参考，不自动成为本次评估能力、缺口或成熟度的事实依据。

**Lifecycle and history**

- R5. 内容方明确撤回的输入版本停止用于生成新建议，包括显式推荐与报告入口触发的隐式计算。
- R6. 撤回影响沿精确版本的运行依赖传递；无该依赖且已确认有效的组合继续使用，版本替换沿革不自动形成运行依赖。
- R7. 历史结果保留原输出、输入版本与可恢复的原始证据，并另外呈现当前来源有效性；依赖受影响不等于内容方已撤回下游内容。
- R8. 结果绑定产生它的答案版本，后续修改答案不得使旧推荐看起来覆盖了新回答。

**Compatibility and boundaries**

- R9. JSON、React、HTML 与 FHIR 对 R1–R8 的表达一致，不因序列化或导出丢失不确定性、来源或当前有效性。
- R10. 交界语义或兼容约定变更采用受影响供需双方批准的 RFC，并按 `docs/15_wp_boundary_contracts.md` 的主版本及过渡规则交付；普通内容交付不增加逐批双边人工签署。
- R11. 保留模块化单体和确定性核心，推演只消费明确传入的版本、回答与评估上下文。
- R12. 保留独立评估会话范围，分别表达参与者类型与场景，不建立机构档案或跨会话机构画像。

### Key Decisions

- **定向落实领域规则。** 以实际行为差距安排工作，暂缓全库 DDD 重构。Governs R1–R12. (session-settled: user-approved — chosen over a full DDD rewrite: 保留已有版本、事务和确定性基础，优先解决明确的语义差距)
- **参考、自报与核验分别表达。** 依据 ADR 0006。Governs R1, R2, R3, R4. (session-settled: user-directed — chosen over inherited type defaults and treating absence as false: 类型知识及信息缺失不能代替本次证据)
- **停止受影响的新推演，保留历史。** 依据 ADR 0007。Governs R5, R6, R7. (session-settled: user-directed — chosen over continued inference from withdrawn inputs and global suspension: 限定影响范围并保留可追溯结果)
- **内容责任与技术接入分开。** 依据 ADR 0004。Governs R10. (session-settled: user-directed — chosen over WP4 deciding upstream meaning and repeated dual sign-off for every delivery: 由内容方确认含义，协议变更才走双边 RFC)
- **V1 保留独立会话。** 依据 ADR 0005。Governs R12. (session-settled: user-directed — chosen over a persistent organization registry: 当前交付不需要机构级历史模型)

### Acceptance Examples

| ID | Covers | Given / When | Expected |
| --- | --- | --- | --- |
| AE1 | R1, R2 | 必要能力未回答，且没有其他依据 | 判断为未知，呈现条件性方向和待补信息 |
| AE2 | R1, R2 | 同一能力分别明确回答 yes、no、unknown | 三种判断不同，未知不经否定变成肯定 |
| AE3 | R3 | 用户完整填写且自报具备能力 | 保留自报和未核验，即使完整度为 1 |
| AE4 | R4 | 类型参考含能力 A，本次没有回答 A | 本次 A 保持未知，其他未列能力不变成已确认缺口 |
| AE5 | R5, R6 | T1 被撤回，R1/Q1/L1 依赖 T1，T2 仅 supersedes T1 | 暂停 A 组合的新推演，已确认有效的 T2 组合继续使用 |
| AE6 | R7, R8, R9 | 结果 E1 后修改答案，再读取 E1 | E1 使用原证据；当前会话不混用 E1 与新回答 |
| AE7 | R5, R7 | 求解期间撤回先提交 | 本次不发布新的有效结果，原有历史仍可读取 |
| AE8 | R5, R6 | 可信撤回先于目标快照到达 | 后续导入/激活仍识别该精确版本不可使用 |
| AE9 | R9, R10 | 旧消费者遇到无法安全表达的新语义 | 明确返回迁移响应，绝不静默删字段后宣称 ready |
| AE10 | R7, R9 | 原 ready 结果的来源现已撤回 | 保留原始结果，当前导出明确历史性质并停止呈现可执行计划 |
| AE11 | R6 | 同一代次中 Q1 撤回，Q2 不依赖 Q1，公共输入仍有效 | Q2 的现有及新会话仍可使用，不把代次成员关系当依赖 |

### Scope Boundaries

全库目录迁移、按 WP 拆分微服务、CQRS、事件溯源平台、RDF/OWL 存储和机构注册表不在本计划内。
实现可复用现有 dataclass、纯求值模块与存储接口，无须为每个名词建立聚合或 Repository。

不新增自动核验服务、核验授权 UI、消息代理、自动撤回恢复、重试平台或新的认证提供方。
当前任务分别用未核验来源标记、授权管理员接入与数据库事务关闭已知差距；出现已批准的核验职责或外部推送要求时再设计对应能力。

#### Deferred to Follow-Up Work

- 核验主体、证据资格及核验流程的正式业务设计；本次只保存和限制证据性质。
- 新的跨 WP 反馈统计协议；v2 未知结果不得被旧统计逻辑解释为明确未触发，新增指标另行确认。

---

## Planning Contract

### Current Evidence

| Seam | Existing behavior | Planning consequence |
| --- | --- | --- |
| `pathfinder/core/compliance.py` | 布尔 AND/OR/NOT，缺失字段比较可能为假 | 增加显式三值结果并检查所有调用方 |
| `pathfinder/core/questionnaire.py`、`pathfinder/adapters/boundary.py` | 能力集合和完整度；映射字段部分丢失 | 契约、适配、模型、回答验证一起改 |
| `pathfinder/core/boundary_validation.py`、`contracts/wp8-rulebundle.schema.json` | v1 主版本硬编码，配对测试仅三类结果 | 版本注册与求值预期按 profile 分派 |
| `pathfinder/services/assessment_service.py` | 已绑定边界的路径要求交卷；旧模式另有推导 | 分开迁移，不能声称所有模式都继承类型能力 |
| `pathfinder/core/repositories/boundary_store.py` | 不可变快照/代次、会话 revision、事务锁、仅 schema v1 | 增量迁移并扩展已有事务边界 |
| `pathfinder/api/schemas.py`、`pathfinder/visualization/adapter.py` | 响应字段过滤；HTML 另有布尔比较 | 显式字段和权威求值轨迹贯通 |
| `pathfinder/fhir/mappers.py` | ready 与其他情况粗粒度映射 | 按业务结果及当前有效性分别映射 |

### Key Technical Decisions

- KTD1. **扩展已有模块边界。** 领域类型放入 `pathfinder/core/models.py`，判断逻辑留在纯核心，服务负责版本、权限上下文和事务协调。落实 R11、R12；不搬动整个目录树。
- KTD2. **新语义使用显式 profile。** 固定 profile 标识和实现版本写入代次、会话及结果；v1 原求值与配对测试保持隔离，v2 使用下方真值表。`BoundaryGeneration` 的构建、问卷版本键、求值器/求解器及验证用配对测试统一按注册表装配，输入 profile 不由客户端任意覆盖。
- KTD3. **能力事实采用逐项 finding。** 包含能力 ID、present/absent/unknown 判断、回答来源、证据引用和核验记录。问卷自报只产生未核验记录；原 `confidence` 保留并标明完整度含义，不能作为核验开关，落实 R3。
- KTD4. **批准的问卷明确绑定回答含义。** v2 单项能力问题将 yes/no/unknown 映射到能力 ID；旧正向多选只声明选中项，明确负向集合才声明不具备，同一版本出现矛盾回答则拒绝。必填验证保留，允许不确定回答的问题需提供批准的 unknown 选项。
- KTD5. **主版本并行，不覆写 v1。** 新增 `pf.questionnaire.v2`、`pf.rulebundle.v2`，未改变含义的 taxonomy/roadmap 保持 v1；新建独立撤回控制消息 `pf.withdrawal.v1`。版本注册表列明允许组合，存储按 profile 保留独立的活跃代次指针，路由及会话始终选择对应 profile；不以最大版本号或 stakeholder_type 猜选，也不新增跨 WP assessment 快照契约。
- KTD6. **公开 API 使用明确 v2 路径。** 问卷及评估创建、回答、推荐、报告、FHIR 增加 v2 对应路由，领域服务共享。过渡期保留 v1 原 profile；G1 完成后才停止 v1 新评估/新推演，并以明确的迁移响应指向 v2。旧历史能安全标记时继续读取，无法表达来源有效性的旧投影返回明确冲突，不将新语义降格成旧 ready。
- KTD7. **撤回采用独立追加记录。** 控制消息携带 notice ID、精确目标列表、目标 producer/contract、理由与来源确认引用；管理员授权与来源内容确认分别记录。管理员核对内容方确认材料后提交接入声明，系统校验材料摘要、精确目标与所有者映射并审计该声明，不把 producer_wp 或引用字符串当作独立身份认证。未到达的快照也可留下精确版本 tombstone；同 notice ID 同内容幂等，冲突内容拒绝。
- KTD8. **结果记录不可变，当前有效性单独观察。** 新建结果记录绑定 result ID、answer_revision、原始回答/findings、实际运行输入集合、profile/实现版本、显式评估日期及原输出。该集合为公共 taxonomy/roadmap/rulebundle、本次选择的 questionnaire 及其传递依赖，代次中其他问卷的成员关系不构成依赖。`answer_revision` 只随回答改变，与存储 CAS revision 分开。result ID、发布审计和当前有效性属于记录/投影元数据，不进入纯推演内容哈希；findings 和未决依据采用稳定顺序。
- KTD9. **在最终提交时重查。** 求解在事务外完成；最终持久化使用与撤回相同的事务级写锁，在同一连接中检查答案 revision 和依赖有效性、写结果并写成功审计。激活与会话创建也在其最终提交的同一锁内重查精确输入有效性。结果若先提交则作为历史保留；撤回若先提交则不得成功发布。内存模式复用进程锁提供相同的单实例语义。
- KTD10. **迁移增加表，不篡改旧证据。** schema v1→v2 增加撤回、结果历史及按 profile 的活跃代次映射表、索引和 runtime grants；已有活跃指针归入 legacy profile。旧会话仅保留实际存有的结果，无法恢复的原回答绑定标记 legacy_unbound，不从当前可变答案伪造原证据；新语义重新评估使用新会话。
- KTD11. **输出消费同一结果和有效性观察。** HTML 删除独立求值路径，API 明确声明嵌套字段，FHIR 与前端消费相同判断/来源/条件/有效性。FastAPI 的响应过滤要求真实 HTTP 验证，单测服务字典不足。[FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/)
- KTD12. **沿用同步 PostgreSQL 事务完成生命周期排序。** 复用现有 advisory transaction lock，无须消息代理或新的分布式事务组件。事务检查与写入必须共享连接；分别调用两个自行开连接的方法不成立。[PostgreSQL 16 locking](https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS)、[psycopg 3.2 transactions](https://github.com/psycopg/psycopg/blob/3.2.0/docs/basic/transactions.rst)

KTD5–KTD7 的共享字段、消息和 KTD6 的切换行为是 RFC 提案内容，不表示其他 WP 已批准。
`docs/15_wp_boundary_contracts.md` `5 已明确语义变化必须升主版本；关闭额外字段的旧 schema 不能靠“可选字段”获得兼容。[JSON Schema object reference](https://json-schema.org/understanding-json-schema/reference/object#additionalproperties)

### High-Level Technical Design

#### Component Boundaries

~~~mermaid
flowchart TB
  C[契约注册与整组验证] --> G[不可变输入代次]
  G --> A[会话与答案版本]
  A --> D[能力 finding 与三值推演]
  D --> S[提交服务]
  L[撤回与依赖有效性] --> S
  S --> E[不可变结果记录]
  E --> P[JSON / React / HTML / FHIR 投影]
  L --> P
~~~

#### Evidence Data Flow

~~~mermaid
flowchart TB
  T[类型参考] --> Q[问卷设计与参考展示]
  Q --> A[本次回答和明确映射]
  A --> F[逐项判断 / 来源 / 核验性质]
  F --> V[条件求值与缺失依据]
  V --> R[候选路径 / 阻断 / 条件方向]
  R --> B[绑定答案版本和快照的结果]
~~~

类型参考进入问卷或参考展示，不直接进入本次 finding，落实 R4。

#### Truth Algebra and DSL

T/F/U 分别表示真、假、未知，v2 采用下表。
这是域求值选择，不要求在 SQL 中执行规则。[PostgreSQL 16 logical operators](https://www.postgresql.org/docs/16/functions-logical.html)

| A | B | A AND B | A OR B |
| --- | --- | --- | --- |
| T | T | T | T |
| T | F | F | T |
| T | U | U | T |
| F | T | F | T |
| F | F | F | F |
| F | U | F | U |
| U | T | U | T |
| U | F | F | U |
| U | U | U | U |

NOT T=F，NOT F=T，NOT U=U。
缺失字段、无依据的 null 或未作断言的能力成员参与实质比较时为 U；明确 false、0 和已声明的否定保持其含义。
v2 的能力集合 contains 判断查询对应 finding：present 为 T、absent 为 F、unknown 为 U；missing_capabilities 的对应判断仅对明确 absent 为 T。
不支持的能力整集合比较在 v2 验证时拒绝，不能退回 Python 集合真假；原始回答字符串与域 Unknown 分开，用于能力前提的规则必须引用批准的能力映射。
`exists` 专门观察回答是否存在，缺失可得到 F，用于提示补信息；不得将其否定解释成能力成立。
无条件规则 `{}` 保留为 T，空 AND/OR 在 v2 验证时拒绝，未知运算符与类型不匹配是错误而非 U。
求值返回明确类型，所有触发判断必须显式匹配 T；配对测试扩展 unknown 预期，图示与编译器不另建求值器。

#### Recommendation Decision Matrix

| Current inputs | Known blocking effect | Critical unresolved effect | Output |
| --- | --- | --- | --- |
| valid | yes | any | blocked，给出已知阻断 |
| valid | no | yes | degraded + conditional_direction + 待补信息 |
| valid | no | no，法规来源未核验 | degraded + 来源警示 |
| valid | no | 仅 preference 未知 | 不单独判为 blocked；未触发动作保留在轨迹 |
| valid | no | none | ready，仍按 R3 标明自报性质 |
| withdrawn / affected | any | any | 不发布新结果；历史读取进入当前有效性投影 |

“关键”沿用当前 exclusion 或显式 block action 的作用含义，不能仅按 eligibility 名称推断。
确定的结构性无路径仍单独说明原因。
`missing_information` 只包含影响整体条件/路径的未知项；`F AND U` 和 `T OR U` 的无关分支不成为必补条件。
矩阵各有效输入行按从上到下的适用优先级选择，法规来源核验与能力自报核验保持独立。

#### Exact Dependency Impact

~~~mermaid
flowchart TB
  T1[T1 被来源方撤回] --> R1[R1 依赖受影响]
  T1 --> Q1[Q1 依赖受影响]
  T1 --> L1[L1 依赖受影响]
  R1 --> L1
  T2[T2 已确认有效] -. supersedes / 不传播 .-> T1
  T2 --> B[另一可用组合]
~~~

依赖闭包按 `manifest.dependencies` 的精确目标计算，路径方向表示“前者被后者使用”，落实 R6。
控制消息与旧版本替换信息不加入此运行依赖图。
评估使用的闭包以 KTD8 的实际运行输入为起点，不能把同代次的全部问卷一起判为当前会话依赖。

#### Lifecycle States

~~~mermaid
stateDiagram-v2
  [*] --> NotReceived
  NotReceived --> Withdrawn: 可信精确版本通知
  NotReceived --> Accepted: 完整接入通过
  Accepted --> Withdrawn: 内容方撤回该版本
  Accepted --> Affected: 运行依赖被撤回
  Affected --> Withdrawn: 内容方另行撤回自身
  Withdrawn --> Withdrawn: 重复通知或同版本重激活
~~~

`Affected` 表示当前不能使用该组合，不表示内容方撤回了该下游快照。
新替代版本使用新身份独立接入，不通过清除旧撤回记录恢复。
拒绝新批次不产生撤回事件，落实 ADR 0007。

#### Publication Ordering

~~~mermaid
sequenceDiagram
  participant S as 推荐服务
  participant K as PostgreSQL 共同写锁
  participant W as 撤回接入
  S->>S: 按绑定回答和代次纯求解
  W->>K: 获取事务锁并追加撤回
  W->>K: 审计并提交
  S->>K: 获取同一事务锁
  S->>K: 重查答案版本和输入有效性
  K-->>S: 受影响，拒绝发布
  Note over S,K: 若结果事务先完成，后续作为历史附加有效性标识
~~~

报表当前有效性来自一次一致的观察，所有投影共用该 lifecycle revision。
缓存只缓存不可变代次，不能缓存“尚未撤回”为持久真值。

#### Compatibility Matrix

| Input / record | Validation and interpretation | Allowed use |
| --- | --- | --- |
| v1 历史结果 | 原 profile 与实际存有的证据 | 历史读取及安全标记的导出 |
| 过渡期 v1 新会话 | v1，明确标记旧语义 | G1 前维持约定的过渡行为，不能冒充 v2 达标 |
| v2 问卷 + v2 规则 + 兼容 v1 分类/路线图 | 注册表声明的 v2 profile | 新语义评估 |
| v2 问卷 + 未声明兼容的 v1 规则 | 拒绝整组激活 | 不猜选或混合求值 |
| 未支持的主版本 | 明确版本错误 | 不降级解释 |
| legacy_unbound 旧记录 | 不补造原始绑定 | 历史展示；当前评估需新会话 |

### Public and FHIR Projection

v2 保留 `ready/blocked/degraded` 顶层结果词汇，另行声明 `recommendation_kind`、逐项 findings、未决条件及当前有效性。
当前有效性独立于原结果状态。
撤回请求使用 `POST /v2/admin/withdrawals`；v2 报告支持显式 result_id，省略时只选择与当前答案版本一致的结果。
v2 报告没有匹配结果时返回“需要生成推荐”的明确响应，不通过读取隐式重算历史。
v1 原有隐式生成行为在过渡期仍必须经过 KTD9。

| Case | HTTP response | Client meaning |
| --- | --- | --- |
| 合法条件性方向或明确受阻 | 200 | 业务结果，按结果与依据展示 |
| 无凭据或无管理员权限 | 401 / 403，沿用既有鉴权 | 不接受该管理操作 |
| 原生请求模型错误 / 域输入错误 | 保留既有 422 / 400 边界 | 修正数据，不把错误变为 Unknown |
| 目标会话或指定结果不存在 | 404 | 不跨会话猜选结果 |
| 输入撤回、答案版本冲突、通知身份冲突、需生成结果或迁移 | 409 + 分开的机器错误码 | 不成功发布；由调用方明确选择后续操作 |
| 当前生命周期状态不可读取 | 503 | 无法确认有效性，不缓存降级为成功 |

FHIR 按 R4 4.0.1 处理请求状态与业务结果：

- 条件性方向：`GuidanceResponse.data-required`，待补信息进入相应数据需求，提议计划为 draft。
- 明确受阻且求值成功：`GuidanceResponse.success`，阻断理由进入输出，不生成可执行 CarePlan；处理失败才使用 failure。
- 仅因法规来源未核验而 degraded：求值已完成时使用 `GuidanceResponse.success`，计划投影为 draft，并给出法规依据警示，不伪造为缺少回答。
- 历史 ready 的来源撤回：保留原处理结果，当前投影呈现失效原因；没有已完成执行证据的计划采用 revoked 终止投影，真实存档中的完成状态不改写。
- Observation 的 final 表示资源工作流状态，不作为能力已核验的证明；FHIR provenance/扩展保留能力依据和精确快照集合。

所有 Bundle 资源引用同一 result ID、答案版本及有效性观察；当前投影版本与存档原结果明确区分。
会话 `status=complete` 只表示推荐已生成，不能推断 CarePlan 已执行完成；本计划不新增执行跟踪，缺少历史完成证据时保留其缺失。
这是 Pathfinder 的映射政策提案，受 HL7 字段含义约束。[GuidanceResponseStatus](https://hl7.org/fhir/R4/codesystem-guidance-response-status.html)、[GuidanceResponse definitions](https://hl7.org/fhir/R4/guidanceresponse-definitions.html)、[RequestStatus](https://hl7.org/fhir/R4/codesystem-request-status.html)

### Rollout and Approval Gates

- G1. 受影响 WP 完成问卷/规则主版本、撤回来源确认和消费者兼容性 RFC；按 `docs/15_wp_boundary_contracts.md` 维持一个里程碑或消费者声明就绪的双主版本窗口。v1 写入切换需列入消费者就绪确认。
- G2. 真实 PostgreSQL 的跨连接/跨进程提交顺序、重启、迁移、最小权限及回滚失败场景均取得通过证据。
- G3. 停止所有旧写入 worker，迁移 schema v2，再启动具备生命周期检查的新 worker；完成本地/预发布输出验收后恢复写入。旧二进制不能成为绕过撤回的回退方案。

~~~mermaid
flowchart TB
  A[RFC 与消费者就绪] --> B[停止旧写入 worker]
  B --> C[受控 schema 迁移]
  C --> D[启动新 worker 并检查数据]
  D --> E[验证完整输出和撤回行为]
  E --> F[恢复新语义写入]
~~~

迁移失败时保持写入关闭并按备份恢复程序处理，避免新旧写入者同时绕过约束。
发布后修复优先保留生命周期约束；如需回退应用，必须使用仍支持 schema v2 和撤回约束的兼容版本。

### Risks and Dependencies

外部正式认可属于发布门槛，不阻止内部合成数据实现。
若 RFC 修改了已确认业务行为，应回到对应 R-ID，不在适配层静默折中。

历史会话可能已经缺少原始答案绑定，KTD10 因而保留不确定性。
现有 `tests/test_boundary_postgres.py` 没有 `TEST_BOUNDARY_DATABASE_URL` 会跳过；跳过不能满足 G2。

---

## Implementation Units

### U1. Versioned contracts and evaluation profiles

**Goal:** 为新语义建立可验证的输入协议和明确版本边界。
**Requirements:** R1–R4、R9、R10；KTD2、KTD4–KTD7。
**Dependencies:** 无。

**Files:**

- 新增 `docs/rfcs/pathfinder-semantic-v2.md`。
- 新增 `contracts/envelope.v2.schema.json`、`contracts/wp4-questionnaire.v2.schema.json`、`contracts/wp8-rulebundle.v2.schema.json`、`contracts/withdrawal.schema.json`。
- 新增 `contracts/samples/wp4-questionnaire.v2.snapshot.json`、`contracts/samples/wp8-rulebundle.v2.snapshot.json`、`contracts/samples/withdrawal.snapshot.json`。
- 新增 `pathfinder/core/contract_registry.py`，修改 `pathfinder/core/boundary_validation.py`、`pathfinder/core/boundary_runtime.py` 和 `scripts/validate_contracts.py`。
- 测试：现有 `tests/test_boundary_contracts.py`，新增 `tests/test_contract_version_profiles.py`。

**Approach:**

1. RFC 逐项说明 KTD2、KTD4–KTD7、输出兼容策略及双方确认位置；没有签署时保持提案状态。
2. 保留 v1 schema 与样例原样，新 envelope/profile 引用新 schema 和允许的未变 v1 输入。
3. 注册表集中管理 contract ID、主版本、producer、schema 与兼容组合；先接入代次的 profile/实际问卷合同键，控制消息走独立接收验证，不可作为运行输入激活。
4. 新配对测试 schema 声明 unknown；在 U3 求值实现就绪前不得激活该 profile。

**Patterns to follow:** `docs/15_wp_boundary_contracts.md` `5/`8；现有 checksum vectors、依赖整组验证和旧配对测试。

**Test scenarios:**

1. Covers AE9. 原 v1 golden samples 与配对测试含义保持一致，旧消费者不被喂入 v2 内容。
2. 合法 v2 组合通过结构、校验和、引用及版本分派；不支持的 major 或混合组合明确失败。
3. 新 unknown 预期在 v2 合法，在旧关闭枚举中失败，失败不得改变已激活代次。
4. 新撤回消息不能进入可激活快照集合，producer/contract 归属不符或缺来源确认引用不能通过接收验证；这不证明来源身份已被自动认证。

**Verification:** schema/版本测试覆盖有效和错误组合；该层证明结构和分派，不证明来源确认真实性或跨进程生命周期。

### U2. Capability findings and questionnaire mappings

**Goal:** 将当前回答变成保留来源的能力判断。
**Requirements:** R1、R3、R4；KTD3、KTD4。
**Dependencies:** U1。

**Files:** 修改 `pathfinder/core/models.py`、`pathfinder/core/questionnaire.py`、`pathfinder/adapters/boundary.py`；新增 `tests/test_capability_findings.py`，扩展 `tests/test_pathfinder_core.py`。

**Approach:**

1. 定义 finding 和显式真值类型，为后续求值提供稳定输入。
2. 按 profile 传递完整 capability mapping，并由同一映射构建能力判断、来源和回答关联。
3. v2 的旧能力集合若仍作为兼容投影，由 findings 派生；unknown 不进入明确缺口集合。
4. 保留填写验证及完整度计算，客户端不能通过自填核验标记升级事实。

**Execution note:** 先以现有必填、多选空数组与 confidence 行为建立特征覆盖，再改变其领域解释。

**Test scenarios:**

1. Covers AE2. yes/no/unknown 分别构成不同判断，未选中的能力仍未知。
2. Covers AE3. 完整自报即使完整度为 1 仍未核验，证据引用不丢失。
3. 正向多选空数组、缺失可选问题、显式负向集合和缺失必填分别得到预定结果。
4. 同一能力同时正负断言、越界能力 ID、畸形回答或客户端强填 verified 被拒绝。
5. 通过 snapshot→adapter→questionnaire→finding 的集成路径验证映射，不只构造域对象。

**Verification:** `tests/test_capability_findings.py` 证明映射与来源，HTTP 序列化由 U7 验证。

### U3. Three-valued evaluation and conditional guidance

**Goal:** 保留条件未知及其对路径可行性的影响。
**Requirements:** R1、R2、R11；KTD2 与 HTD 真值/结果矩阵。
**Dependencies:** U1、U2。

**Files:** 修改 `pathfinder/core/compliance.py`、`pathfinder/core/models.py`、`pathfinder/core/solver.py`、`pathfinder/core/recommend.py`、`pathfinder/core/boundary_runtime.py`、`pathfinder/core/boundary_validation.py`、`pathfinder/core/rules/loader.py`；新增 `tests/test_condition_truth.py`，扩展 `tests/test_curated_rules.py`、`tests/test_boundary_contracts.py`。

**Approach:**

1. 将字段解析、原子比较、复合条件和未决依据纳入同一权威求值结果。
2. 触发、阻断及候选方向消费显式真值；False 与 Unknown 都不执行动作，但 Unknown 的可行性影响必须保留。
3. 完成 v2 代次的问卷、求值器与求解器装配，让激活配对测试和运行求解选择同一 profile；编译器继续只编译数据。
4. 将未决条件、影响判断及来源写入结果轨迹，供 U7 使用。

**Execution note:** 新语义先用完整有限真值表与旧 profile 黄金用例验证，再接求解器。

**Test scenarios:**

1. Covers AE1, AE2. AND/OR 九种组合与三个 NOT 结果均正确，嵌套表达式不依赖 Python truthiness。
2. absent、null、false、0、未作断言的列表成员、exists、空复合节点及错误类型按 HTD 区分。
3. Covers AE1. 未知的 exclusion/block 条件得到条件性方向，明确阻断仍 blocked。
4. 无关未知分支不生成必补任务；未知 preference 不单独判为不可行。
5. 同一 v2 paired test 在导入和实际推荐中结果一致；v1 黄金预期不被新求值悄悄重释。

**Verification:** 单测覆盖代数，边界/求解集成验证到结果语义；不以单独修改 status 字符串作为完成证据。

### U4. Persistent lifecycle and immutable result storage

**Goal:** 为撤回与结果历史增加可跨 worker 读取的持久状态。
**Requirements:** R5–R8；KTD7–KTD10、KTD12。
**Dependencies:** U1、U2。

**Files:** 新增 `pathfinder/core/boundary_lifecycle.py`；修改 `pathfinder/core/repositories/boundary_store.py`、`scripts/migrate_boundary_storage.py`；新增 `tests/test_boundary_lifecycle.py`，扩展 `tests/test_boundary_postgres.py`。

**Approach:**

1. 在纯生命周期模块实现精确依赖影响分析，存储层保留通知及目标身份。
2. 以版本化 schema 迁移创建追加式撤回、结果历史、profile 活跃代次映射及所需索引/grants，保护旧快照与原输出。
3. 增加结果保存所需的单连接事务操作，复用原锁及会话 CAS。
4. 按 KTD10 迁移已有 session 结果；无法证实的旧证据绑定显式保留未知。

**Patterns to follow:** 已有 append-only 触发器、schema_version 检查、显式迁移脚本与无 DDL 权限 runtime 测试。

**Test scenarios:**

1. Covers AE5. 直接和传递依赖受影响，supersedes-only 的替代版本不被误暂停。
2. Covers AE8. 未见快照的可信通知能持久记录，后续接入不能漏过。
3. 同通知重送幂等，身份冲突、跨 producer 冲突、非法目标被拒绝且不部分写入。
4. 原 schema v1 数据迁移后存储内容、规范化哈希及原结果值保留，重复迁移安全，旧 schema 或错误权限给出明确诊断；不要求恢复未保存的 JSON 文本字节。
5. 存储层可分别保存 v1/v2 活跃代次映射，一个 profile 的指针变化不改另一个；完整运行装配及会话选择由 U5/U6 验证。
6. 新历史表与审计在真实 PostgreSQL 中不可变，runtime 角色能正常追加而无须拥有 schema。

**Verification:** 纯测试只证明依赖算法；真实 `tests/test_boundary_postgres.py` 必须证明迁移、权限、重启和跨进程可见性。

### U5. Answer revisions and guarded recommendation publication

**Goal:** 每个新结果使用匹配的证据，并在提交时满足当前输入有效性。
**Requirements:** R4–R8、R11；KTD8–KTD10。
**Dependencies:** U3、U4。

**Files:** 修改 `pathfinder/services/assessment_service.py`、`pathfinder/services/derived_readiness.py`、`pathfinder/core/repositories/boundary_store.py`；新增 `tests/test_assessment_revisions.py`，扩展 `tests/test_derived_readiness.py`、`tests/test_boundary_activation.py`、`tests/test_boundary_postgres.py`。

**Approach:**

1. 绑定会话 profile 和 answer_revision；所有保留的 v1/v2 写入路径更新答案后都使当前结果引用失效，旧结果记录仍可选择读取。
2. 将旧 WP2 推导限于参考/演示，生产新语义会话必须使用本次回答；服务的问卷/规则版本键来自代次 profile，去除固定 v1 键的推演假设。
3. 完成计算后调用 KTD9 的单事务保存；冲突时不自动换代次、不复用过期答案发布。
4. 所有可能计算结果的入口经过同一发布操作，现有报告隐式生成路径也在其中。

**Execution note:** 先覆盖“改答案后读取旧推荐”的实际服务路径及旧模式差异，再接新记录存储。

**Test scenarios:**

1. Covers AE4. 类型含 A、当前无 A 回答，不能生成本次 A 为 present 或其他能力 absent 的事实。
2. Covers AE6. v1 过渡路径与 v2 路径的 E1 后修改回答，当前报告都不混用；显式 E1 读取返回原答案证据。
3. Covers AE7. 撤回先于提交，成功结果及成功审计均不落库；答案先变更同样拒绝过期发布。
4. 结果先提交、撤回后提交，结果保留并在后续读取时呈现当前变化。
5. 冷/热缓存 worker、独立进程与重启都执行同一检查；写结果或审计失败完整回滚。

**Verification:** 服务测试覆盖各入口；CAS/撤回竞争与事务原子性必须由真实 PostgreSQL 双连接/进程场景证明。

### U6. Trusted withdrawal intake and historical validity

**Goal:** 接收有来源依据的撤回，并将影响落实到激活与历史读取。
**Requirements:** R5–R7、R9、R10；KTD7、KTD9、KTD11。
**Dependencies:** U4、U5。

**Files:** 修改 `pathfinder/services/assessment_service.py`、`pathfinder/core/boundary_runtime.py`、`pathfinder/api/main.py`、`pathfinder/api/schemas.py`；扩展 `tests/test_boundary_lifecycle.py`、`tests/test_boundary_activation.py`、`tests/test_boundary_postgres.py`、`tests/test_api_contract_behavior.py`。

**Approach:**

1. 在既有管理员鉴权基础上增加 KTD7 接收流程和来源确认记录，追加操作人及内容方确认的分别审计。
2. 激活最终检查本次整批候选；会话可用性及发布只检查 KTD8 的实际运行输入集合，不能用代次成员关系扩大影响，也不能以重新激活同版本取消 tombstone。
3. 历史读取选择结果记录，使用一次有效性观察组装附加标识，不重算或修改原结果。
4. 按 R6 返回具体受影响版本和依赖原因，不把整个来源 WP 的无关组合一并停用。

**Test scenarios:**

1. 非管理员、缺接入确认、producer/contract 归属或材料目标不一致、通知身份冲突各自失败；授权且有确认声明的通知成功，不声称能独立识别上游身份伪造。
2. Covers AE5, AE8. 通知先到、整组激活、相同 ID 重激活与独立替代版本分别得到正确结果。
3. 激活/会话创建的最终提交与撤回竞争时，撤回先提交则拒绝该受影响输入；双 profile 选择正确且不自动切换旧会话。
4. Covers AE11. 单一 Q1 被撤回后，同代次 Q2 的现有及新会话继续使用已确认有效的实际输入。
5. Covers AE10. 历史读取有原输出与当前有效性，重复读取不改变原结果哈希。
6. 无匹配历史结果且来源已撤回的报告请求，不能通过隐式计算绕过禁用。
7. 数据库生命周期读取失败不退回缓存声称有效，而按现有服务错误机制明确失败。

**Verification:** HTTP 测试证明权限、结构和实际字段；数据库测试证明持久性，不能由管理员身份推导内容确认真实性。

### U7. API and consumer projection parity

**Goal:** 所有用户出口保留领域语义与证据绑定。
**Requirements:** R2、R3、R7–R10；KTD6、KTD8、KTD11 与 Public and FHIR Projection。
**Dependencies:** U2、U3、U5、U6。

**Files:**

- 修改 `pathfinder/api/main.py`、`pathfinder/api/schemas.py`、`pathfinder/api/openapi.py`。
- 修改 `pathfinder/visualization/schemas.py`、`pathfinder/visualization/adapter.py`、`pathfinder/visualization/renderer.py`。
- 修改 `pathfinder/fhir/mappers.py`、`pathfinder/fhir/export_service.py`。
- 修改 `frontend/src/main.tsx`，新增仅供界面投影使用的 `frontend/src/assessmentSemantics.ts`。
- 测试：`tests/test_api_contract_behavior.py`、`tests/test_openapi_contract.py`、`tests/test_visualization.py`、`tests/test_fhir_export.py`；新增 `frontend/scripts/assessmentSemantics.test.mjs`。

**Approach:**

1. 添加 KTD6 的 v2 路由与明确嵌套模型，复用领域服务，保留版本化的错误和迁移响应。
2. 将权威求值轨迹传给 HTML，删除其独立比较造成的语义分歧。
3. 为前端建立小型投影函数，依照现有 Node test + TypeScript transpile 模式验证，不把求值搬到浏览器。
4. 按本节 FHIR 政策生成一致引用，历史 QuestionnaireResponse 使用结果记录的原回答。
5. 同步在线 OpenAPI 与离线导出，更新版本注册和外部引用解析以支持 `.v2.schema.json` 文件；不放宽所有对象的 extra 规则来绕过契约。

**Test scenarios:**

1. Covers AE1, AE3. 真实 HTTP 返回 findings、来源、未决条件与核验性质，嵌套字段没有被过滤。
2. Covers AE6, AE10. 同一结果在 JSON、HTML、React、FHIR 显示同一证据与当前有效性。
3. FHIR 条件性、明确受阻、仅法规来源未核验和来源撤回分别符合已选 R4 映射，内部引用正确；会话 complete 不被映射为计划执行完成。
4. v1 旧请求、明确迁移响应、v2 错误结构、认证、媒体类型及在线/离线 OpenAPI 一致。
5. 前端投影测试覆盖未知、自报、阻断及撤回文案；真实浏览器确认相应页面无可执行状态误导。

**Verification:** Node 测试证明投影函数，不能替代 DOM/浏览器检查；后端 HTTP/FHIR/HTML 测试分别覆盖真实传输和导出。

### U8. Compatibility evidence and controlled rollout

**Goal:** 将实现交付为可审阅、可迁移并有真实验收证据的变更。
**Requirements:** R9–R12；G1–G3。
**Dependencies:** U1–U7。

**Files:** 修改 `docs/15_wp_boundary_contracts.md`、`docs/16_wp_boundary_data_protocol.md`、`scripts/build_protocol_html.py`、`scripts/build_scailed_ddd_html.py`；重建 `docs/16_wp_boundary_data_protocol.html`、`docs/19_scailed_ddd_design.html`；修改 `docs/rfcs/pathfinder-semantic-v2.md`；按 `scripts/build_openapi.py` 与 `scripts/build_swagger_ui.py` 更新 `docs/18_pathfinder_openapi.json`、`docs/18_pathfinder_openapi.yaml`、`docs/18_pathfinder_swagger.html`；新增 `docs/runbooks/pathfinder-semantic-cutover.md`，必要时更新 `deploy/smoke-test.sh`。

**Approach:**

1. 将版本/profile、迁移/拒绝响应和内容责任记录到协议及生成文档，基线 ADR 保留原含义。
2. 产出受控 schema 迁移与发布 runbook，包括旧 worker 停写、runtime grants、验证及失败处理。
3. 汇集 Verification Contract 的结果与消费者兼容矩阵，区分内部证据和待签署的正式认可。
4. 执行 G1–G3 的发布验收准备；缺外部签署时明确停留在内部可验证交付，不宣称生产目标已实现。

**Test expectation:** 此单元不新增领域行为测试；验证 U1–U7 的整体验收及部署 smoke。若 smoke 脚本新增判断，复用其现有验证方式并证明错误状态不会给出成功。

**Verification:** 文档与生成物无漂移，迁移在已有 schema v1 的隔离库演练通过，所有阻断发布门槛有明确证据或未满足记录。

---

## Verification Contract

下列命令供实施阶段在项目环境与隔离测试服务中使用，本计划编写不运行应用或测试。
新增测试文件仅在对应单元实现后存在。

| Area | Concrete check | Required evidence |
| --- | --- | --- |
| 域判断 | `python3 -m pytest tests/test_capability_findings.py tests/test_condition_truth.py tests/test_pathfinder_core.py tests/test_curated_rules.py` | 真值表、来源、必填、否定与条件方向 |
| 契约及激活 | `python3 -m pytest tests/test_contract_version_profiles.py tests/test_boundary_contracts.py tests/test_boundary_activation.py` | v1/v2 验证、求值 profile、旧 golden 与错误组合 |
| 会话与旧推导 | `python3 -m pytest tests/test_assessment_revisions.py tests/test_derived_readiness.py tests/test_boundary_lifecycle.py` | 不混用证据、参考不继承、精确撤回 |
| 真实持久化 | `python3 -m pytest tests/test_boundary_postgres.py`，配置隔离的 `TEST_BOUNDARY_DATABASE_URL` | 迁移、跨进程、竞争、重启、事务失败与最小权限；不得跳过 |
| 出口契约 | `python3 -m pytest tests/test_api_contract_behavior.py tests/test_openapi_contract.py tests/test_visualization.py tests/test_fhir_export.py` | 真实 HTTP、schema、HTML 与 Bundle 一致 |
| 前端 | `npm --prefix frontend test`；`npm --prefix frontend run build` | 既有测试及新投影测试、编译结果 |
| 规范漂移 | `python3 scripts/build_openapi.py --check`，以及离线 Swagger 内嵌规范等价检查 | 同一规范源、无悬空引用、版本示例可验证 |
| 全量回归 | `python3 -m pytest tests/ -v`；本地隔离部署满足前提后 `make gate` | 新旧差异归因，无新增失败，不把跳过视为通过 |
| 浏览器验收 | 在本地/预发布访问条件性、自报、改答案、指定历史结果及撤回页面 | 桌面与手机的实际交互和字段显示，无误导 ready/active |

根 Makefile 没有 `release:validate` 目标，使用现有 `make gate` 及本表专项门槛。
已有失败若在执行时复现，应记录独立基线证据后归因，不预先宣称历史失败仍然存在。
迁移命令、数据库恢复及生产凭据仅写入受控 runbook，不在测试中引用真实生产库。

### Coverage Boundaries

- 纯域与 Node 投影测试不证明跨 worker、HTTP 字段或浏览器 DOM 行为。
- PostgreSQL 场景必须控制真实提交顺序，覆盖暖缓存 worker；线程锁测试不能替代。
- API/FHIR/HTML 断言需使用同一 AE 固定样例，验证结果 ID、答案版本和 lifecycle revision。
- 样例通过结构校验不等于来源内容已被业务确认；G1 独立验收。

---

## Definition of Done

- R1–R12 的对应 AE 和单元场景有实施证据，U1–U8 均按其 Verification 完成。
- v1 schema/快照含义、原始历史结果与独立会话边界得到保留，迁移不补造核验或原始证据。
- 实际 HTTP、React、HTML、FHIR 无语义丢失，在线及离线规范一致。
- 真实 PostgreSQL 的 G2 全部通过，无跳过替代或缓存绕过。
- G1 与 G3 完成才可宣称生产切换完成；任何未满足项明确列为发布阻断。
- 删除实施中被放弃的实验代码、临时兼容旁路和无用依赖，保留用户原有无关工作区修改。

---

## Appendix

### Sources and Research

规范性本地来源：`docs/domain-modeling/2026-11-26-pathfinder-semantic-baseline.md`、`docs/domain-modeling/pathfinder-boundaries/CONTEXT.md`、`CONTEXT-MAP.md`、`docs/adr/0003-in-memory-deterministic-core.md`、`docs/adr/0004-source-wps-retain-content-authority.md`、`docs/adr/0005-v1-independent-assessment-sessions.md`、`docs/adr/0006-type-capabilities-remain-reference-information.md`、`docs/adr/0007-withdrawn-inputs-stop-new-recommendations.md`、`docs/15_wp_boundary_contracts.md`。

实现定位：本计划各 U-ID 的现有路径；`tests/test_boundary_postgres.py` 提供真实数据库测试模式，`frontend/scripts/stakeholderCatalog.test.mjs` 提供前端投影测试模式。
所列新增文件均是计划产物，不能假定仓库已具备相应能力。

来源、修订与失效关系参考 [W3C PROV-DM](https://www.w3.org/TR/prov-dm/)，仅借用概念区分，不引入语义网存储。
具体三值、并发和框架依据已在 KTD/HTD 附近引用；这些资料不代替 SCAILED 的内容所有者决定。

