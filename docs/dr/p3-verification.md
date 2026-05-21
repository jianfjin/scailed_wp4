# SCAILED WP4 — DR Implementation: P3 (4-Layer Verification)

## 实施概要 / Summary

> **P3 四层恢复验证已完成。** 每周六 04:00 cron 自动执行 sha256 → schema restore → AGE catalog → total rows 四层验证。首次全通过：V1 ✅ V2 ✅ (4 tables) V3 ✅ (1g/4l) V4 ✅ (2800 rows)。

**Date**: 2026-05-21
**Status**: ✅ Complete
**Resolution**: Joint 16/0

---

## 4-Layer Verification

| Layer | Content | Method | Frequency | Result |
|-------|---------|--------|-----------|--------|
| V1 | File integrity | `sha256sum -c checksums.sha256` | Daily (in backup.sh) | ✅ |
| V2 | Schema restore | `pg_restore --schema-only` → temp DB → table count | Weekly | ✅ 4 tables |
| V3 | AGE catalog | Graph count + label count vs live DB | Weekly | ✅ 1g/4l |
| V4 | Data volume | Total row count + DB size vs catalog | Weekly | ✅ 2800 rows |

---

## Files

| File | Purpose |
|------|---------|
| `deploy/verify_restore.sh` | 4-layer verification script |
| `deploy/backup.sh` | V1 checksum generation (daily) |

---

## How It Works

```
verify_restore.sh (weekly)
│
├─ V1: sha256sum -c ────── verify all backup files match checksums
│
├─ V2: pg_restore ──────── create temp DB, restore schema-only, count tables
│
├─ V3: AGE catalog ─────── compare ag_graph count + ag_label count vs live
│
└─ V4: total rows ──────── ANALYZE → compare sum(n_live_tup) + db size vs catalog
```

## Cron

```
# SCAILED WP4 — DR verification: V2+V3+V4 weekly (Sat 04:00)
0 4 * * 6 /home/jin/projects/scailed_wp4/deploy/verify_restore.sh >> /backups/pg/verify_cron.log 2>&1
```

Runs one hour after the daily backup, so it always verifies the fresh backup.

---

## Verification

```bash
# Run manually
bash deploy/verify_restore.sh

# Check logs
tail -20 /backups/pg/verify.log
tail -20 /backups/pg/verify_cron.log
```

---

## Related

- [P1+P2 Implementation](./p1-p2-backup-implementation.md)
- [Joint DR Resolution](../plans/2026-05-20-joint-dr-resolution.md) — 16/0 vote
