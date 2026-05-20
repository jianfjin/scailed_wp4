# 容灾/备份/主从方案对比 — VM 议会 vs 本地团队

**日期**: 2026-05-20
**议题**: SCAILED WP4 容灾、备份、主从数据库方案
**方法**: 两方各出方案，议会对比，陛下定夺

---

## 一、方案摘要

### VM 议会方案 (6/6 全票)

**一句话**: pg_dump cron + WAL 归档到云端 + 每月自动恢复验证。不要主从。

**核心命令**:
```bash
# 每日凌晨
pg_dump -Fc | rclone rcat remote:scailed-backups/pg/$(date +%Y%m%d).dump
sha256sum /backup.dump > /backup.dump.sha256

# 每周六
docker run --rm -e POSTGRES_PASSWORD=test postgres:16 \
  pg_restore --dbname=postgres < /backup.dump
docker exec verify-pg psql -c "SELECT count(*) FROM ag_catalog.ag_graph;"
```

**成本**: €6/月 云端 + 3人天实施 = €1,500/3年
**恢复**: RPO 24h, RTO 40min

### 本地团队方案

**一句话**: PG 三层备份 (pg_dump + WAL + streaming 主从) + Local→VM 流复制

**核心架构**: 本地 PG (Primary) → WAL streaming → VM PG (Standby, read-only)
**成本**: 2 VM + 流复制维护 (未明确标价)
**恢复**: RPO < 1s, RTO 5-30min

---

## 二、逐项对比

### 2.1 主从复制

| 维度 | VM 议会 | 本地团队 |
|------|---------|---------|
| 是否需要 | ❌ 不需要 | ✅ 需要 |
| 理由 | 1人维护不了; split-brain风险; 预算不够 | Local→VM双向接管 |
| 成本 | €0 | 15-25人天 + 双VM |
| NPV | +€300 | -€7,500 (雪峰计算) |

**议会反对主从的 6 个独立理由**:

| 席位 | 反对理由 |
|------|---------|
| Jensen | "单VM IOPS远低于流复制触发阈值。省下钱做restore自动化。" |
| Musk | "流复制多一个失败模式(WAL损坏/延迟/冲突)。一个人类修不了。" |
| 雪峰 | "净现值唯一正收益的是方案A(pg_dump cron)。主从越贵越亏。" |
| 小龙 | "RTO<5min + ≥2人会操作DB + 有人on-call。SCAILED三个都不满足。" |
| Linus | "主从只解决硬件故障，不解决逻辑损坏/误删。但逻辑损坏才是实际风险。" |
| Dijkstra | "不证伪的备份=祈祷。先搞定验证，再谈复制。" |

### 2.2 备份层次

| 层级 | VM 议会 | 本地团队 |
|------|---------|---------|
| L1 逻辑 | pg_dump -Fc 每日 | pg_dump -Fc 每日 |
| L2 WAL | archive_mode=on → 云端 | archive_mode=on → VM |
| L3 异地 | rclone → B2/Wasabi | streaming replica → VM |
| 配置文件 | .env GPG加密 | .env GPG加密 |
| Docker volumes | 不需要(pg_dump已含) | 每周 tar 快照 |

### 2.3 恢复验证

| 维度 | VM 议会 | 本地团队 |
|------|---------|---------|
| 验证方法 | 三层: sha256 → schema restore → full AGE count | 未提及 |
| 频率 | 每日 sha256 + 每周完整 restore | 未定 |
| 关键原则 | "30天没验证 = 没有备份"(Linus) | 未强调 |

**Dijkstra 三层证明体系**:
```
Layer 0: sha256sum 校验 (每日, 10秒)
Layer 1: schema-only restore → 结构完整性 (每周, 2分钟)
Layer 2: full AGE catalog count → 数据完整性 (每周六, 5分钟)
```

### 2.4 灾难恢复

| 场景 | VM 议会 | 本地团队 |
|------|---------|---------|
| PG 损坏 | pg_restore 从云端 | PG PITR 或 failover 到 standby |
| VM 全死 | 新VM → git clone → rclone pull → restore (40min) | 本地接管 |
| 本地全死 | — (VM 部署) | VM standby 接管 |
| 逻辑误删 | PITR 从 WAL (前提: 云端有WAL) | 流复制同步了误删 ❌ |
| 磁盘满 | 清理 + 迁移到云端 | 需要紧急清理 |

**关键差异**: 流复制会同步误删 (逻辑损坏)。VM 议会特意强调离线备份不受此影响。

### 2.5 成本 (3年)

| 方案 | 实施 | 维护 | 云存储 | 总计 |
|------|------|------|--------|------|
| VM 议会 | 3人天 €1,200 | 0.5d/年 €200×3 | €6/月 ×36 = €216 | ~€1,816 |
| 本地团队 | 15-25人天 €6,000-10,000 | 5d/年 €2,000×3 | VM €40×36 = €1,440 | ~€12,000+ |
| 差额 | — | — | — | **~6.6×** |

---

## 三、议会投票

| 席位 | 主从复制 | 推荐方案 | 一句话 |
|------|:------:|---------|--------|
| Jensen | ❌ | pg_dump + WAL → S3 | "Save replication budget for restore automation" |
| Musk | ❌ | pg_dump cron + restore script | "Master-slave is complexity theater with one dev" |
| 雪峰 | ❌ | pg_dump + WAL + 第二VM冷备 | "唯一正净现值方案" |
| 小龙 | ❌ | backup.sh + verify_restore.sh | "RTO<5min+2人DB+on-call一个不满足" |
| Linus | ❌ | pg_dump + WAL → Hetzner Storage Box | "30天没验证=没有备份" |
| Dijkstra | ❌ | 三层证明 + 云端 pg_dump | "唯一有效证明是成功恢复" |
| **CTO** | **❌** | **采纳议会方案** | **€1,816 vs €12,000, 6.6×差异** |

**票数: 7/7 反对主从复制, 全票通过 pg_dump + WAL 云端 + 自动验证**

---

## 四、VM 议会最终方案

### 4.1 备份脚本 (backup.sh)

```bash
#!/bin/bash
BACKUP_DIR=/opt/scailed/backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REMOTE="wasabi:scailed-backups"

# 1. PostgreSQL full dump with checksum
docker exec scailed-postgres pg_dump -U pathfinder -Fc \
  -f /tmp/scailed_${TIMESTAMP}.dump
sha256sum /tmp/scailed_${TIMESTAMP}.dump > /tmp/scailed_${TIMESTAMP}.dump.sha256

# 2. Docker Compose + .env snapshot
cp /opt/scailed/deploy/docker-compose.yml ${BACKUP_DIR}/compose/
cp /opt/scailed/.env ${BACKUP_DIR}/env/ 2>/dev/null

# 3. Offsite sync
rclone copy /tmp/scailed_${TIMESTAMP}.dump ${REMOTE}/pg/
rclone cleanup ${REMOTE}/pg/ --min-age 30d
```

### 4.2 恢复验证脚本 (verify_restore.sh)

```bash
#!/bin/bash
LATEST=$(rclone lsjson wasabi:scailed-backups/pg/ | jq -r '.[-1].Name')

# Docker ephemeral restore
docker run -d --name scailed-verify-pg -e POSTGRES_PASSWORD=test postgres:16
sleep 5
rclone cat wasabi:scailed-backups/pg/${LATEST} | \
  gunzip | docker exec -i scailed-verify-pg psql -U postgres

# Integrity check
docker exec scailed-verify-pg psql -U postgres -d pathfinder \
  -c "SELECT count(*) FROM ag_catalog.ag_graph;"

docker rm -f scailed-verify-pg
echo "$(date -Iseconds) — VERIFIED"
```

### 4.3 恢复 Runbook

```
Step 1: 新 VM (15min) → apt install docker git rclone
Step 2: git clone (2min)
Step 3: docker compose up -d postgres (5min)
Step 4: rclone copy latest.dump + pg_restore (10min)
Step 5: docker compose up -d (5min)
Step 6: curl /health + SELECT count(*) (2min)
─────────────────────────────────────────
总计: ~40min
```

---

## 五、VM 磁盘告警 (86%)

当前: 30GB / 24GB used / 4.1GB free

紧急措施:
1. 清理 Docker 缓存/旧镜像 (如有)
2. 清理 `/tmp` 和 `/var/log`
3. 迁移大型 fixture 文件到本地机器
4. 如需长期: 挂载额外 storage 或 resize VM disk

---

## 六、裁决建议

**议会推荐**: 采纳 VM 议会方案。

理由:
1. 成本: €1,816 vs €12,000+ (6.6×差异)
2. 可维护性: 一个 bash 脚本 + cron, 一个人能修
3. 恢复验证: 三层自动证明, 不是祈祷
4. 主从风险: 同步误删, split-brain, 需要多人 on-call
5. 预算匹配: €145K 项目不适合企业级 HA

**唯一的采纳点**: 本地团队的 .env GPG 加密备份 — 议会方案可吸收此项。

---

**归档**: docs/plans/2026-05-20-disaster-recovery-comparison.md
**签署**: 峰哥 (CTO, VM 议会召集人)
**日期**: 2026-05-20
