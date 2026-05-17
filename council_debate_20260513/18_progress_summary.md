# SCAILED WP4 Pathfinder — 项目进展总览

**日期**: 2026-05-17
**状态**: Phase 0 (M1-M3) 执行中

## P0 — e2e闭环验证 ✅

| 项目 | 结果 | 环境 |
|------|------|------|
| 应用层e2e | audit_chain_valid: true, 0 blockers | 本地 PG16+AGE1.5.0 |
| Docker全栈部署 | 5容器 healthy (traefik/frontend/backend/postgres/redis) | 本地 Docker |
| Docker 7 bugs修复 | 全部修复并推送 | — |
| Demo video录制 | 待做 | — |

### Docker 7 bugs修复清单

| Bug | 根因 | 修复 |
|-----|------|------|
| uvicorn崩溃 | pip --no-deps缺依赖 | 去掉--no-deps |
| Python找不到包 | pip --prefix不在sys.path | PYTHONPATH补/install |
| Traefik无路由 | v3.3 Docker client太老 | 升至v3.7 |
| 路由404 | ratelimit@docker自引+被过滤 | 砍掉中间件 |
| Backend无路由 | 缺traefik.enable标签 | 补标签 |
| /api被截胡 | internal dashboard优先级9e18 | 关掉--api.insecure |
| Frontend unhealthy | wget走IPv6, nginx只监听IPv4 | 127.0.0.1 |

## P1 — AGE runtime连线VM端 ✅

| 项目 | 结果 |
|------|------|
| asyncpg安装 | ✅ |
| PG16连接 | VM→SSH:5433→本地PG16 |
| AGE扩展 | ✅ |
| USE_AGE=1 demo | 0 blockers, audit_chain_valid: true |

## 代码基线

| 模块 | 文件 | 行数 | 测试 |
|------|------|------|------|
| core/models.py | 领域模型 | 200 | — |
| core/solver.py | CSP路径求解器 | 64 | ✅ |
| core/graph.py | InMemory图引擎 | 71 | ✅ |
| core/graph_age.py | AGE图引擎 | 320 | 5 tests |
| core/rules/ | 规则引擎(parser/validator/compiler/loader) | ~300 | ✅ |
| core/audit.py | 审计日志 | ~50 | ✅ |
| core/compliance.py | 合规评估 | ~30 | ✅ |
| core/questionnaire.py | 问卷引擎 | ~50 | ✅ |
| adapters/demo_data.py | Mock数据 | 242 | ✅ |
| services/assessment_service.py | 编排服务(双backend) | ~160 | ✅ |
| api/main.py | FastAPI(AGE lifespan) | 157 | 2 tests |
| frontend/src/main.tsx | React SPA | 148 | — |
| tests/ | 测试套件 | 3 files | 13/13 pass |

## 文档基线

| 文档 | 状态 |
|------|------|
| 00_council_resolution.md (CN+EN) | 8/8融合裁决，3轮辩论记录 |
| architecture-spec.html | §02a-f 完整 (含Mermaid图, Agent-D对比) |
| 17_next_steps_resolution.md | 5席P0-P6优先级排序 |
| email_to_lu_zhao_v3.md | 待发送 |
| deploy/deployment-architecture.html | SVG部署架构图 |
| deploy/docker-compose.yml | 5容器, 7 bugs fixed |
| deploy/Dockerfile.* | backend/frontend/postgres |
| openspec/ | add-merged-pathfinder-v1 (60%完成) |

## 部署验证

```
$ sudo docker ps
scailed-traefik     Up   traefik:v3.7    :80
scailed-frontend    Up   nginx+React     :80 (internal)
scailed-backend     Up   FastAPI 3.12    :8000 (internal)
scailed-postgres    Up   PG16+AGE        :5432 (internal)
scailed-redis       Up   Redis 7         :6379 (internal)
```

## 基础设施

| 链路 | 方向 | 端口 |
|------|------|------|
| SSH forward | 本地→VM gateway | 8643→8642 |
| SSH reverse webhook | VM→本地 webhook | 8645→8644 |
| SSH reverse PG | VM→本地 PostgreSQL | 5433→5432 |
| Cloudflare tunnel | 公网→VM webhook | offline-powder...trycloudflare.com |

## 预算跟踪 (Xuefeng审计)

| 阶段 | 人天 | 金额 |
|------|------|------|
| Pre-contract已完成 | 30天 | €21,000 |
| M1-M3预算余额 | 32天 | €22,500 |
| M1-M3必须项 | 14天 | €9,800 |
| M1-M3缓冲 | 18天 | €12,700 |

## 待办 (P2-P6)

```
P2 [ ] 3.2 API schema锁定 + error model (3-5种)
P3 [ ] 前端交互式表单 (200行React, 1天)
P4 [ ] 2.7 core tests + p95 latency (demo scale)
P5 [ ] 4.4 clean install验证
P6 [ ] 发送email_to_lu_zhao_v3
```

## 推迟到Phase 1 (M4-M8)

- 4.1 文案打磨
- 4.3 Stakeholder review sessions
- 5.x V2 scoping
- Demo数据扩展 (8-10 stakeholders, 15-20 rules)
