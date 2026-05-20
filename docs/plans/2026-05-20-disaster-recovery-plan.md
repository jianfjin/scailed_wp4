# SCAILED WP4 — 容灾/备份/主从方案 (本地团队版)

> 议会授权：峰哥(贺迷思) 领本地团队  
> 版本：v1.0 — 2026-05-20  
> 对标：VM 议会版（峨眉峰，deepseek-v4-pro）

---

## 一、现状审计

### 1.1 拓扑

```
┌─ Local (jin-X555LAB) ─────────────────────┐
│  Docker Compose (8 containers)             │
│  ├─ traefik       :80 (reverse proxy)      │
│  ├─ frontend      nginx + React SPA        │
│  ├─ backend       FastAPI :8000 (1 worker) │
│  ├─ postgres      PG16 + Apache AGE        │
│  ├─ redis         7-alpine                 │
│  ├─ wp2-mock      stakeholder taxonomy     │
│  ├─ wp3-mock      roadmap graph            │
│  └─ wp8-mock      rules engine             │
│  Volumes:                                   │
│  ├─ scailed_pgdata     ~47 MB              │
│  └─ scailed_redis_data                     │
│  SSH bridge → VM (8643, 8647, 8645, 2222)  │
└────────────────────────────────────────────┘

┌─ VM (GCP e2-micro, 34.57.82.51) ──────────┐
│  Same Docker Compose stack                 │
│  Disk: 30 GB (4.1 GB free ⚠️)              │
│  RAM:  1.9 GB (626 MB free ⚠️)             │
│  Hermes agent: deepseek-v4-pro             │
│  tmux: work-0 (attached), vm-work          │
└────────────────────────────────────────────┘
```

### 1.2 当前备份状态

| 资源 | 备份方式 | 频率 | 状态 |
|------|----------|------|------|
| 源码 + Dockerfile | GitHub (jianfjin/scailed_wp4) | 每次 push | ✅ |
| Mock 数据 | GitHub (services/mock/fixtures/) | 提交时 | ✅ |
| PG 数据 (AGE 图) | **无** | — | ❌ |
| Docker volumes | **无** | — | ❌ |
| 配置文件 | GitHub (.env 不入库) | 手动 | ⚠️ |

### 1.3 风险点

| 风险 | 影响 | 当前缓解 |
|------|------|----------|
| VM 磁盘满 (86%) | PG 写入失败，容器崩溃 | 无 |
| VM OOM (626MB 空闲) | PG/backend 被杀 | 无 |
| PG 数据损坏 | 1000 节点 DAG + 规则数据丢失 | 无 |
| VM 被删除/欠费 | 服务全停 | 本地可接管 |
| 本地硬件故障 | 开发环境丢失 | VM 可接管 |

---

## 二、备份策略

### 2.1 PostgreSQL — 三层备份

#### L1: 逻辑备份（pg_dump）

```bash
# 每日全量 dump，保留 7 天
0 3 * * * pg_dump -U pathfinder -h localhost -p 5432 \
  -Fc -f /backups/pg/scailed_$(date +\%Y\%m\%d).dump
```

- 格式：custom (`-Fc`)，支持并行恢复
- 包含：schema + data + AGE graph
- 保留：本地 7 天，rsync 到 VM 30 天

#### L2: WAL 归档（连续）

```sql
-- postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'rsync -a %p jin@192.168.1.x:/backups/pg/wal/%f'
```

- 实现 PITR（Point-in-Time Recovery）
- WAL 段每 16MB 或 5 分钟归档一次

#### L3: 异地副本（主从复制，见第三章）

### 2.2 Docker Volumes

```bash
# 每周快照（停服 30s 或不锁表 pg_dumpall）
0 4 * * 0 docker run --rm -v scailed_pgdata:/src:ro \
  -v /backups/volumes:/dst alpine \
  tar czf /dst/pgdata_$(date +\%Y\%m\%d).tar.gz -C /src .
```

### 2.3 配置文件

```bash
# .env 加密备份
0 2 * * * gpg -c ~/.hermes/.env > /backups/config/hermes_env.gpg
```

### 2.4 备份汇总

| 层级 | 内容 | 频率 | 保留期 | 位置 |
|------|------|------|--------|------|
| L1 | pg_dump (custom) | 每日 03:00 | 本地 7d, VM 30d | /backups/pg/ |
| L2 | WAL archive | 连续 | 7d | /backups/pg/wal/ |
| L3 | 主从 streaming | 实时 | — | VM standby |
| V1 | Docker volumes | 每周日 04:00 | 4 周 | /backups/volumes/ |
| C1 | .env 加密 | 每日 02:00 | 30d | /backups/config/ |

---

## 三、PostgreSQL 主从复制

### 3.1 架构

```
┌─ Local (Primary) ──────────┐    streaming     ┌─ VM (Standby) ───────────┐
│  PG16 + AGE                 │ ←─────────────→  │  PG16 + AGE (read-only)  │
│  WAL sender                 │   WAL stream     │  WAL receiver            │
│  scailed_pgdata (read/write)│                  │  scailed_pgdata_standby  │
└─────────────────────────────┘                  └──────────────────────────┘
```

### 3.2 配置

**Primary (本地)**

```ini
# postgresql.conf
wal_level = replica
max_wal_senders = 5
wal_keep_size = 1024    # 1GB WAL 保留
hot_standby = on

# pg_hba.conf
host replication pathfinder 34.57.82.51/32 md5
```

**Standby (VM)**

```ini
# postgresql.conf
hot_standby = on
primary_conninfo = 'host=<local-ip> port=5432 user=pathfinder password=changeme'
primary_slot_name = 'vm_standby_slot'
```

### 3.3 初始化 Standby

```bash
# 1. 在 primary 创建复制槽
psql -U pathfinder -c "SELECT * FROM pg_create_physical_replication_slot('vm_standby_slot');"

# 2. 在 standby 拉取基础备份
pg_basebackup -h <local-ip> -U pathfinder -D /var/lib/postgresql/data -P -R -S vm_standby_slot

# 3. 启动 standby
docker compose up -d postgres-standby
```

### 3.4 切换（Failover）

```bash
# 将 standby 提升为 primary
psql -U pathfinder -h 34.57.82.51 -c "SELECT pg_promote();"
```

---

## 四、容灾场景

### 4.1 场景矩阵

| 场景 | 检测 | RTO | RPO | 恢复步骤 |
|------|------|-----|-----|----------|
| **PG 数据损坏** | backend /health 报错 | 5 min | <1 min (WAL) | PITR 恢复到故障前 |
| **VM 宕机** | SSH bridge 断连 | 2 min | <1 min | 本地 primary 继续服务；Traefik DNS 切换到本地 IP |
| **本地宕机** | VM agent 检测 bridge | 2 min | <1 min | VM standby → promote；用户访问 VM |
| **双站点全毁** | 手动确认 | 30 min | <24h | git clone → docker compose up → pg_restore 最新 dump |
| **磁盘满** | cron 监控 `df -h` | 5 min | 0 | 清理旧备份/dump → 扩容 |

### 4.2 自动故障检测

```bash
#!/bin/bash
# /etc/cron.d/healthcheck — 每分钟

# 检测 local PG
if ! pg_isready -h localhost -p 5432; then
  curl -X POST http://localhost:8647/webhooks/local-agent-bridge \
    -d '{"message":"⚠️ Local PG down"}'
fi

# 检测 VM reachable
if ! ssh -o ConnectTimeout=5 jianfjin@34.57.82.51 "pg_isready -h localhost" 2>/dev/null; then
  echo "VM unreachable" >> /var/log/scailed-dr.log
fi
```

---

## 五、实施计划

### Phase 1: 备份（立即，<2h）

- [ ] 创建 `/backups/pg/` `/backups/volumes/` `/backups/config/` 目录
- [ ] 部署 cron job：每日 pg_dump
- [ ] 部署 cron job：每周 volume 快照
- [ ] 部署 cron job：.env 加密备份
- [ ] 测试 pg_restore 恢复流程

### Phase 2: WAL 归档（1d）

- [ ] 修改 postgresql.conf（wal_level=replica, archive_mode=on）
- [ ] 配置 archive_command
- [ ] 测试 PITR 恢复

### Phase 3: 主从复制（2d）

- [ ] VM 部署 standby PG 容器
- [ ] 配置 primary WAL sender
- [ ] pg_basebackup 初始化
- [ ] 验证 streaming 延迟 <1s

### Phase 4: 自动故障切换（3d）

- [ ] 部署 healthcheck cron（每分钟）
- [ ] 配置告警 webhook
- [ ] 文档化 failover 手册
- [ ] 演练：模拟 VM 宕机 → standby promote

### Phase 5: 备份异地同步（1d）

- [ ] 本地 → VM rsync pg_dump（每日）
- [ ] VM → 本地 rsync（反向）

---

## 六、资源估算

| 资源 | 当前 | 方案后 | 增量 |
|------|------|--------|------|
| VM 磁盘 | 4.1 GB free | ~2 GB free | +2 GB (备份 + WAL) |
| VM 内存 | 626 MB free | ~400 MB free | +226 MB (standby PG) |
| 本地磁盘 | 充足 | ~500 MB | +500 MB (备份) |
| Cron jobs | 0 | 5 | +5 |

### 磁盘告警阈值

```
VM 磁盘 < 2GB → 清理 7 天前备份
VM 磁盘 < 1GB → 停止 WAL 归档 + 告警
VM 磁盘 < 500MB → 紧急：迁移到更大实例
```

---

## 七、与 VM 议会版对比预案

> 待 VM 峰哥提交后填充

| 维度 | 本地版 | VM 版 | 陛下裁决 |
|------|--------|-------|----------|
| 备份策略 | pg_dump + WAL + volume snap | ? | |
| 主从方向 | Local→VM (streaming) | ? | |
| 故障切换 | 手动 promote + DNS | ? | |
| 监控 | cron healthcheck | ? | |
| 成本 | 0（现有资源） | ? | |

---

*本地团队：峰哥 (CTO) + Linus (Arch) + Guido (CLA)*  
*待 VM 峨眉峰提交议会辩论版*
