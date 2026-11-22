# Pathfinder OpenAPI：7 项问题修复计划

日期：2026-11-22。范围：上一轮对 `pathfinder/api/` 与 `docs/18_pathfinder_*` 的接口审查。

目标：调用方从在线 OpenAPI、JSON/YAML 或离线 Swagger 获取相同契约，能正确认证、执行示例并处理真实错误。

## 修复与验收

| ID | 优先级 | 问题 | 修复方案 | 验收证据 |
| --- | --- | --- | --- | --- |
| F1 | P1 | 在线规范缺少导入 body，Report/FHIR 引用悬空，与导出不一致 | 将契约扩展迁入 API 模块，由缓存的 `app.openapi()` 调用；导出脚本只序列化同一结果；通过 FastAPI 的响应模型注册组件 | 在线、JSON、YAML、Swagger 内嵌规范完全相同；所有本地引用可解析；OpenAPI 验证通过 |
| F2 | P1 | 大部分受保护操作没有 Bearer security，Swagger 不发送凭证 | 通过共享 HTTPBearer 依赖声明凭证，接入现有令牌检查；覆盖全部业务与 dashboard 操作 | 无凭证 401，demo 可访问业务但不能管理，admin 可访问两者；浏览器 Authorize 后实际请求含 Authorization |
| F3 | P1 | 文档错误为平铺对象，实际有 `detail` 外层 | 新增 `ApiErrorEnvelope`，统一错误响应声明，保留线上 JSON 格式及原生 422 格式 | 实际 400/401/403/404/409/429/503 响应按对应 schema 验证 |
| F4 | P2 | legacy 导入错误声明为 SnapshotEnvelope，示例不可执行 | 分别声明 WP2/WP3 平铺结构，复用 WP8 现有规则 schema；提供独立可执行示例并标记 deprecated | 每个示例通过 schema 校验，提交相应旧端点返回 200；不修改现有输入语义 |
| F5 | P2 | 已知 409/429/503 未声明 | 为会话写冲突声明 409，为限流及数据库/未激活边界声明 429/503 与错误 envelope | 通过真实限流和受控数据库/冲突故障验证状态与响应体 |
| F6 | P2 | 文档承诺复用 active 依赖，运行时要求完整批次 | 明确本次批次须包含运行时所需 taxonomy、roadmap、questionnaire、rulebundle 及精确的 `manifest.dependencies`；区分历史 `supersedes` | 完整批次成功；已激活后单独提交规则包仍返回 400，原 generation 保持不变 |
| F7 | P2 | 缺失 assessment 在部分端点返回 400 | answers、recommendations、report 中先处理 KeyError 并返回统一 404/NOT_FOUND | 五个 assessment 读取/操作端点对不存在 ID 均返回 404；真实输入错误保持 400，写冲突保持 409 |

## 实施顺序

1. 抽取在线/离线共享的 OpenAPI 生成逻辑，修正原生响应模型声明；在线文档默认访问当前服务 origin，文件方式打开的离线 Swagger 默认选择 localhost:8000。
2. 接入 Bearer 依赖，修正错误 envelope、已知状态以及缺失资源映射。
3. 修正 legacy schema/示例和完整依赖闭包说明。
4. 增加针对上述行为的契约回归测试，纳入现有 OpenAPI CI。
5. 重新生成 JSON、YAML、Swagger；执行契约、API、边界激活、FHIR 回归与浏览器验证。

## 兼容与范围

- 保留现有 demo/admin 令牌、权限划分以及开发环境报告/dashboard 的 query token 访问；生产环境继续仅接受 header。
- 保留错误响应 `{"detail":{"error":"...","detail":"..."}}` 和 legacy 平铺输入；不将 legacy 改为边界 envelope。
- PostgreSQL 模式继续禁用 legacy 导入；批量边界导入继续执行完整批次原子激活。
- 不调整规则求值、FHIR 安全状态、数据库持久化策略或其他工作区修改。
- 上轮验证已有两项 FHIR 状态断言失败（success/data-required、active/draft）；本轮需确认原因并单独记录，不能通过放宽安全状态消除断言。

## 检查命令

使用隔离 Python 环境，并为依赖外部 mock 的现有测试启动本地 WP2/WP3/WP8 服务。

```bash
python -B scripts/build_openapi.py
python -B scripts/build_swagger_ui.py
python -B scripts/build_openapi.py --check
python -B -m pytest tests/test_openapi_contract.py tests/test_api_contract_behavior.py -q
python -B -m pytest tests/test_api.py tests/test_boundary_activation.py tests/test_fhir_export.py -q
```

浏览器检查：打开离线 Swagger，授权 Bearer，执行 questionnaires 与 dashboard 查询，验证实际请求头及页面无 JavaScript 错误。

设计依据：[FastAPI 自定义 OpenAPI](https://fastapi.tiangolo.com/how-to/extending-openapi/)、[HTTPBearer](https://fastapi.tiangolo.com/reference/security/#fastapi.security.HTTPBearer)、[附加响应模型](https://fastapi.tiangolo.com/advanced/additional-responses/)。

## 实施结果（2026-11-22）

F1–F7 均已完成：

- `pathfinder/api/openapi.py` 统一在线与导出契约，包含边界/legacy schema、可执行示例、依赖闭包及错误媒体类型声明。
- `pathfinder/api/main.py`、`middleware.py`、`dashboard.py` 接入共享 Bearer 依赖；Report/FHIR 原生注册模型；缺失 assessment 映射到 404。
- `pathfinder/api/schemas.py` 新增 `ApiErrorEnvelope`；答案/推荐操作声明 409，受保护操作声明 429，数据库/边界不可用声明 503。
- `scripts/build_openapi.py` 仅导出 `app.openapi()`；JSON/YAML/Swagger 已同步生成，在线默认同源，离线默认 localhost:8000。
- OpenAPI CI 增加行为契约测试、Swagger 内嵌规范一致性和相关文件触发条件。

验证结果：

| 检查 | 结果 |
| --- | --- |
| `scripts/build_openapi.py --check` | 通过，JSON/YAML 无漂移 |
| `openapi_spec_validator` | 通过，OpenAPI 3.1 有效 |
| `test_openapi_contract.py` + `test_api_contract_behavior.py` | **46 passed**；无需外部数据库或 mock 服务 |
| `test_api.py` + `test_boundary_activation.py` + `test_fhir_export.py` + `test_request_logger.py` | **65 passed，2 failed**；使用本地 WP2/WP3/WP8 mock 服务 |
| 独立基线复现 | 从未修改的 `dbf0d6d` 导出代码，在相同环境复现同样两项 FHIR 断言失败 |
| Chrome / Playwright | 离线和 HTTPS 托管两种方式均加载 20 个操作；授权后 questionnaires/dashboard 各自请求返回 200、携带 Bearer，页面 JavaScript 错误为 0 |
| `git diff --check`（本次文件） | 通过 |

浏览器请求通过本地测试桥送入真实 FastAPI app；HTTPS 域名为测试域名，不代表已部署到生产环境。

既有 FHIR 失败具体为 `test_care_plan_from_report_maps_next_steps_as_activities`（预期 active，实际 draft）与 `test_guidance_response_from_report_maps_ready_recommendation`（预期 success，实际 data-required）。本次未修改其领域逻辑或安全状态；这两项仍需单独处理。JSON/FHIR 成功响应本身已通过新增的真实响应 schema 校验。
