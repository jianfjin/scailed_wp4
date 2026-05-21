# SCAILED WP4 — 容灾/备份方案：联合决议

**日期**: 2026-05-20
**方法**: VM 议会 (6 席) + 本地议会 (9 席) 联合辩论，逐项投票
**裁定**: 陛下

---

## 一、联合投票结果

| # | 议题 | VM 议会 | 本地议会 | 联合结果 |
|---|------|:--:|:--:|:--:|
| 1 | 主从复制 Local→VM | 6/0 NO | 9/0 NO | **15/0 否决** |
| 2 | 云端异地存储 (B2/Wasabi) | 6/0 YES | 9/0 YES | **15/0 通过** |
| 3 | 强制恢复验证 (自动化) | 6/0 YES | 9/0 YES | **15/0 通过** |
| 4 | 预算 €1,816/3年 | 6/0 YES | 9/0 YES | **15/0 通过** |

**15 席全票一致。主从复制被永久否决。**

---

## 二、最终方案

### 备份层次

```
L1: pg_dump -Fc 每日 03:00 → 本地保留 7 天
L2: WAL 连续归档 → archive_mode=on
L3: rclone 每日同步 → Wasabi (优先) 或 Backblaze B2
L4: 本地保留 pg_dump 第二副本 (本地团队附加)
```

### 异地存储

**Wasabi 优先** (Jensen: 无 egress fee)。Backblaze B2 为备选。

```bash
rclone sync /backups/pg/ wasabi:scailed-backups/pg/
```

Lifecycle policy: 30 天保留，自动过期。

### 恢复验证 — 四层证明

| 层级 | 内容 | 频率 | 自动化 |
|------|------|------|--------|
| V1 | sha256sum 文件完整性 | 每日 (备份后立即) | ✅ cron |
| V2 | pg_restore schema-only | 每周六 04:00 | ✅ cron |
| V3 | AGE catalog count 校验 | 每周六 04:00 | ✅ cron |
| V4 | 抽样 row count | 每月第一个周六 | ✅ cron |

验证脚本用 pytest 编写，CI 每次 push 跑。

### 预算

上限: €1,816/3年。执行目标: **€800 以内**。

| 项目 | 月费 | 3年 |
|------|------|-----|
| Wasabi 100GB | ~€6 | €216 |
| 脚本开发 | — | 2 人天 |
| 总计 | — | ~€800 |

### 不需要的

- ❌ 主从流复制 (15/0 否决)
- ❌ VM standby 作为备份目标
- ❌ Patroni / etcd / HAProxy
- ❌ 第二台 VM 作为热备

---

## 三、VM 自身备份 (Linus 反问)

VM (GCP e2-micro) 不运行 PostgreSQL 或 Docker。仅运行 Hermes agent。

| 数据 | 备份方式 | 状态 |
|------|---------|------|
| Hermes skills | GitHub (jianfjin/hermes-skills) | ✅ |
| Hermes profiles | 导出到 GitHub (待定) | ⚠️ |
| Hermes state.db | 文本导出 + git (待实施) | ❌ |
| Projects | GitHub (jianfjin/scailed_wp4) | ✅ |
| Session logs | 可重建 | N/A |

**待办**: VM Hermes state.db 通过 cron 导出到 git repo。

---

## 四、VM 磁盘清理 (紧急)

| 清理前 | 清理后 |
|--------|--------|
| 30GB / 24GB used / 4.1GB free (86%) | 30GB / 21GB used / 7.1GB free (75%) |

释放 3.0 GB: npm cache 1.5G, Playwright 631M, pip/uv/apt/logs 900M。

---

## 五、实施顺序

| 阶段 | 内容 | 估时 |
|------|------|------|
| P1 | backup.sh 脚本 + cron | 0.5d |
| P2 | rclone → Wasabi 配置 | 0.5d |
| P3 | verify_restore.sh (四层验证) | 1d |
| P4 | pytest 测试用例 | 0.5d |
| P5 | DR runbook (干净VM真炸一次) | 0.5d |
| **总计** | | **3 人天** |

---

## 六、签署

| 方 | 席位 | 票数 |
|----|------|------|
| VM 议会 | Musk/Dijkstra/Linus/Jensen/雪峰/小龙 + CTO | 7/0 |
| 本地议会 | 峰哥主持, 9 席全票 | 9/0 |
| **联合** | **16 席** | **16/0** |

**陛下已阅，裁定生效。**

---

**归档**: docs/plans/2026-05-20-joint-dr-resolution.md
**日期**: 2026-05-20
