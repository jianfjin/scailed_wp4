# SCAILED WP4 — DR Runbook (P5)

## 实施概要 / Summary

> **P5 灾难恢复手册。** 覆盖 5 种故障场景，从本地 Docker 崩溃到异地全毁。每场景含恢复步骤、预估时间、验证清单。目标 RPO ≤ 24h，RTO ≤ 1h。

**Date**: 2026-05-21
**Status**: ✅ Complete
**Resolution**: Joint 16/0

---

## System Profile

| Item | Value |
|------|-------|
| Database | PostgreSQL 16 + Apache AGE 1.5.0 |
| DB size | ~9.6 MB (9,559 kB) |
| Backup size | ~72 KB (dump + schema + catalog) |
| Local backup | `/backups/pg/` — 7-day retention |
| Cloud backup | Cloudflare R2 `scailed-backups/pg/` — €0 |
| Docker volumes | `scailed_pgdata`, `scailed_redis_data` |
| Containers | 8 (traefik, frontend, backend, postgres, redis, wp2/3/8-mock) |
| Deploy path | `~/projects/scailed_wp4/deploy/` |
| RPO target | ≤ 24 hours (daily backup at 03:00) |
| RTO target | ≤ 60 minutes |

---

## Disaster Scenarios

### S1: PostgreSQL Corruption (Most Likely)

**Trigger**: Bad migration, `DROP TABLE`, filesystem error on pgdata volume.

**Impact**: Database unreadable. Application returns 500 errors.

**Recovery**:

```
Step 1: Stop application containers (prevent writes to broken DB)
  cd ~/projects/scailed_wp4/deploy
  docker compose stop backend frontend

Step 2: Verify backup integrity
  bash deploy/verify_restore.sh
  # Must show: ALL CLEAN — 4-layer verification passed

Step 3: Wipe corrupted database
  docker compose stop postgres
  docker volume rm scailed_pgdata
  docker volume create scailed_pgdata

Step 4: Start fresh PostgreSQL
  docker compose up -d postgres
  sleep 10  # wait for AGE init scripts

Step 5: Restore from latest backup
  LATEST_DUMP=$(ls /backups/pg/latest/pathfinder_*.dump)
  docker cp "$LATEST_DUMP" scailed-postgres:/tmp/restore.dump
  docker exec scailed-postgres pg_restore -U pathfinder -d pathfinder \
    --clean --if-exists /tmp/restore.dump

Step 6: Verify restored data
  bash deploy/verify_restore.sh

Step 7: Restart application
  docker compose up -d backend frontend
  curl -f http://localhost/health
```

**RTO**: ~15 minutes
**RPO**: 0–24 hours (last backup)

---

### S2: Docker Host Disk Failure

**Trigger**: Disk corruption, accidental `rm -rf`.

**Impact**: All containers, volumes, and local backups lost.

**Recovery**:

```
Step 1: Set up new host (or reinstall OS)
  # Clean Ubuntu 24.04 minimal install
  sudo apt update && sudo apt install -y docker.io git rclone

Step 2: Clone repo
  git clone https://github.com/jianfjin/scailed_wp4.git ~/projects/scailed_wp4

Step 3: Configure rclone for R2
  bash ~/projects/scailed_wp4/deploy/setup-r2.sh \
    <account_id> <access_key> <secret_key>

Step 4: Pull latest backup from R2
  mkdir -p /backups/pg
  rclone sync r2:scailed-backups/pg/ /backups/pg/latest/

Step 5: Build and start containers
  cd ~/projects/scailed_wp4/deploy
  docker compose up -d --build
  sleep 30  # wait for all healthchecks

Step 6: Copy dump into container and restore
  DUMP=$(ls /backups/pg/latest/pathfinder_*.dump)
  docker cp "$DUMP" scailed-postgres:/tmp/restore.dump
  docker exec scailed-postgres pg_restore -U pathfinder -d pathfinder \
    --clean --if-exists /tmp/restore.dump

Step 7: Verify
  bash deploy/verify_restore.sh
  curl -f http://localhost/health

Step 8: Re-establish cron
  crontab /tmp/scailed-crontab  # or re-add:
  # 0 3 * * * ~/projects/scailed_wp4/deploy/backup.sh >> /backups/pg/cron.log 2>&1
  # 0 4 * * 6 ~/projects/scailed_wp4/deploy/verify_restore.sh >> /backups/pg/verify_cron.log 2>&1
```

**RTO**: ~40 minutes
**RPO**: 0–24 hours

---

### S3: Cloudflare R2 Unavailable

**Trigger**: R2 outage, token expiry, account issue.

**Impact**: Cloud sync fails. Local backups continue normally.

**Recovery**:

```
Step 1: Check R2 status
  rclone ls r2:scailed-backups/pg/
  # If 403/401: token expired — recreate in Cloudflare dashboard
  # If timeout: R2 regional outage — wait, or switch to fallback

Step 2: Fallback to Wasabi/B2
  # Configure alternative rclone remote
  rclone config create wasabi s3 \
    provider=Wasabi \
    endpoint=s3.eu-central-1.wasabisys.com \
    access_key_id=<wasabi_key> \
    secret_access_key=<wasabi_secret>

Step 3: Set SCAILED_RCLONE_REMOTE=wasabi in backup.sh env
  # Or manually sync for now:
  rclone sync /backups/pg/latest wasabi:scailed-backups/pg/

Step 4: Update cron env if permanent
  # Add to crontab:
  SCAILED_RCLONE_REMOTE=wasabi
  0 3 * * * .../backup.sh ...
```

**RTO**: ~5 minutes (local backup unaffected, just switch remote)

---

### S4: Complete Site Loss (Fire/Flood)

**Trigger**: Physical destruction of local machine.

**Impact**: Everything local gone. Only R2 backup survives.

**Recovery**:

```
Step 1: Provision new machine
  # Any x86_64 Linux host with ≥8GB RAM, ≥30GB disk
  # Install: Ubuntu 24.04, docker.io, git, rclone

Step 2: Restore from cloud (same as S2 Steps 2–8)
  git clone + rclone pull + docker compose up + pg_restore + verify

Step 3: Restore Hermes agent config (if applicable)
  git clone <hermes-skills-repo>
  # Re-configure hermes profiles, webhooks, SSH keys

Step 4: Re-establish VM bridge (if needed)
  # Follow hermes-bidirectional-bridge skill
```

**RTO**: ~60 minutes
**RPO**: 0–24 hours
**Data loss risk**: Only data created after last backup (≤24h)

---

### S5: Silent Data Corruption (Hardest to Detect)

**Trigger**: Bit rot, buggy application code, AGE graph inconsistency.

**Impact**: Application appears normal but data is wrong. Users see stale/incorrect results.

**Detection**: Weekly `verify_restore.sh` will catch row count and catalog mismatches.

**Recovery**:

```
Step 1: Identify corruption scope
  bash deploy/verify_restore.sh
  # V4 will flag: "total rows mismatch: catalog=2800 live=2500"
  # V3 may flag: "AGE mismatch: backup(1g/4l) vs live(1g/2l)"

Step 2: Identify when corruption started
  for dir in /backups/pg/202*; do
    bash deploy/verify_restore.sh "$dir"  # point to old backup
  done
  # Find last clean backup before corruption

Step 3: Point-in-time recovery
  # Restore from last known-good backup
  LAST_GOOD=/backups/pg/20260520_030000/pathfinder_*.dump
  docker cp "$LAST_GOOD" scailed-postgres:/tmp/restore.dump
  docker exec scailed-postgres pg_restore -U pathfinder -d pathfinder \
    --clean --if-exists /tmp/restore.dump

Step 4: Re-apply any legitimate changes since that backup
  # Manual: re-run data imports, migrations, user actions
  # Document what was lost for stakeholder communication

Step 5: Run full verification
  bash deploy/verify_restore.sh
```

**RTO**: ~30 minutes (plus re-application of lost changes)
**RPO**: Depends on when corruption started (detection gap)

---

## Quick Reference Card

```
┌──────────────────────────────────────────────────────────┐
│  SCAILED WP4 DR — Quick Reference                        │
├──────────────────────────────────────────────────────────┤
│  Emergency steps (any scenario):                         │
│                                                          │
│  1. DON'T PANIC. Local + R2 = two independent copies.   │
│  2. Stop app to prevent further writes if DB is suspect.│
│  3. Run: bash deploy/verify_restore.sh                   │
│  4. Identify scenario (S1–S5 above).                    │
│  5. Follow scenario procedure.                          │
│                                                          │
│  Key paths:                                              │
│    Local backups:  /backups/pg/                          │
│    Cloud backups:  r2:scailed-backups/pg/                │
│    Deploy scripts: ~/projects/scailed_wp4/deploy/        │
│    Docker compose: ~/projects/scailed_wp4/deploy/        │
│                                                          │
│  Key commands:                                           │
│    Verify:  bash deploy/verify_restore.sh                │
│    Backup:  bash deploy/backup.sh                        │
│    Restore: pg_restore -U pathfinder -d pathfinder       │
│              --clean --if-exists <dump>                  │
│    R2 pull: rclone sync r2:scailed-backups/pg/ /backups/ │
│                                                          │
│  RTO: ≤ 60 min    RPO: ≤ 24 h    Cost: €0               │
└──────────────────────────────────────────────────────────┘
```

---

## Test Log

| Date | Scenario | Result | RTO | Notes |
|------|----------|--------|-----|-------|
| 2026-05-21 | V1–V4 verify | ✅ 26/26 pass | N/A | CI green |
| 2026-05-21 | S1 dry-run | ✅ All steps verified | ~15 min | Schema restore OK |

---

## Related

- [P1+P2 Implementation](./p1-p2-backup-implementation.md)
- [P3 Verification](./p3-verification.md)
- [Joint DR Resolution](../plans/2026-05-20-joint-dr-resolution.md) — 16/0
