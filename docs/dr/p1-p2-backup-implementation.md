# SCAILED WP4 — DR Implementation: P1+P2 (Backup + Cloud Sync)

## 实施概要 / Implementation Summary

> **P1+P2 容灾备份已部署完成。** 每日 03:00 cron 自动执行 pg_dump → sha256 → rclone → Cloudflare R2。本地 7 天留存，云端异地 R2（€0 免费额度）。联合议会 16/0 全票通过。

**Date**: 2026-05-21
**Status**: ✅ Complete
**Budget**: €0 (Cloudflare R2 免费额度)
**Resolution**: Joint 16/0 (VM 6 + Local 9 + CTO)

---

## Overview

Implemented phases P1 and P2 of the disaster recovery plan ratified by the joint council on 2026-05-20.

| Phase | Content | Status |
|-------|---------|--------|
| P1 | backup.sh — pg_dump + sha256 + AGE catalog + 7-day retention + cron | ✅ |
| P2 | rclone → Cloudflare R2 sync (€0, auto-detect) | ✅ |

---

## Architecture

```
cron @ 03:00 daily
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  backup.sh                                          │
│                                                     │
│  ┌──────────┐   ┌──────────┐   ┌───────────────┐   │
│  │ pg_dump  │ → │ sha256   │ → │ rclone sync   │   │
│  │ -Fc      │   │ + AGE    │   │ → R2 (€0)     │   │
│  │ + schema │   │ catalog  │   │               │   │
│  └──────────┘   └──────────┘   └───────────────┘   │
│       │              │                │             │
│       ▼              ▼                ▼             │
│  /backups/pg/   checksums       Cloudflare R2       │
│  (7-day local   .sha256         scailed-backups/pg  │
│   retention)                                        │
└─────────────────────────────────────────────────────┘
```

---

## Files

| File | Purpose |
|------|---------|
| `deploy/backup.sh` | Main backup script (P1+P2) |
| `deploy/setup-r2.sh` | One-time R2 rclone configuration |

---

## Artifacts per Backup

Each run produces a timestamped directory:

```
/backups/pg/20260521_142231/
├── pathfinder_20260521_142231.dump          # pg_dump -Fc (50 KB)
├── pathfinder_20260521_142231_schema.sql    # Schema-only dump (6.5 KB)
├── pathfinder_20260521_142231_catalog.json  # AGE graph metadata
└── checksums.sha256                          # V1 file integrity
```

Total: ~57 KB per backup.

---

## R2 Cloud Sync

| Item | Value |
|------|-------|
| Provider | Cloudflare R2 |
| Bucket | `scailed-backups` |
| Region | Western Europe (WEUR) |
| Cost | **€0** (10 GB free tier, using 0.0006%) |
| Sync method | `rclone sync --checksum` |
| Trigger | Automatic in backup.sh (skips gracefully if R2 not configured) |

**Fallback**: If `r2` remote is not configured, backup.sh skips cloud sync and logs a warning. Local backup is always safe.

---

## R2 Token (2026-05-21)

- **Permission**: Admin Read & Write
- **TTL**: Forever
- **Token ID**: `cfat_GQdul...` (stored in rclone config, not in repo)
- **Endpoint**: `https://52fdf946227d32558d000f6208377c87.r2.cloudflarestorage.com`

---

## Cron

```
# SCAILED WP4 — PostgreSQL daily backup at 03:00
0 3 * * * /home/jin/projects/scailed_wp4/deploy/backup.sh >> /backups/pg/cron.log 2>&1
```

---

## Environment Variables (optional overrides)

| Variable | Default | Description |
|----------|---------|-------------|
| `SCAILED_PG_CONTAINER` | `scailed-postgres` | Docker container name |
| `SCAILED_PG_USER` | `pathfinder` | PostgreSQL user |
| `SCAILED_PG_DB` | `pathfinder` | Database name |
| `SCAILED_BACKUP_ROOT` | `/backups/pg` | Local backup directory |
| `SCAILED_RETENTION_DAYS` | `7` | Local retention policy |
| `SCAILED_RCLONE_REMOTE` | `r2` | rclone remote name |
| `SCAILED_RCLONE_PATH` | `scailed-backups/pg` | R2 path prefix |

---

## R2 Configuration (one-time)

```bash
bash deploy/setup-r2.sh <account_id> <access_key> <secret_key>
```

Or interactive:
```bash
bash deploy/setup-r2.sh
```

---

## Verification

```bash
# Run backup manually
bash deploy/backup.sh

# Check R2
rclone ls r2:scailed-backups/pg/

# Check cron
crontab -l | grep backup
```

---

## Related Documents

- [Joint DR Resolution](./2026-05-20-joint-dr-resolution.md) — 16/0 council vote
- [Joint Vote Rebuttal](../plans/2026-05-20-joint-vote-rebuttal.md) — VM council rebuttal
- [DR Comparison](../plans/2026-05-20-disaster-recovery-comparison.md) — Original DR options
