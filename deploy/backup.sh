#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# SCAILED WP4 — PostgreSQL Backup (P1+P2: dump + cloud sync)
# 联合决议 (2026-05-20 v2, 16/0): pg_dump + sha256 + R2 sync + 7-day retention
# P1: pg_dump -Fc + schema + AGE catalog + sha256 ✅
# P2: rclone → Cloudflare R2 (€0) / Wasabi / B2 (auto-detect) ✅
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

# ─── Config ───────────────────────────────────────────────────────────
CONTAINER="${SCAILED_PG_CONTAINER:-scailed-postgres}"
PG_USER="${SCAILED_PG_USER:-pathfinder}"
PG_DB="${SCAILED_PG_DB:-pathfinder}"
BACKUP_ROOT="${SCAILED_BACKUP_ROOT:-/backups/pg}"
RETENTION_DAYS="${SCAILED_RETENTION_DAYS:-7}"
LOG_FILE="${BACKUP_ROOT}/backup.log"

# ─── Setup ────────────────────────────────────────────────────────────
TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_ROOT}/${TS}"
mkdir -p "${BACKUP_DIR}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"; }

# ─── Check container is running ───────────────────────────────────────
if ! docker inspect --format='{{.State.Running}}' "${CONTAINER}" 2>/dev/null | grep -q true; then
    log "FATAL: Container ${CONTAINER} is not running. Abort."
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════
# V1: Full dump (custom format — pg_restore compatible)
# ═══════════════════════════════════════════════════════════════════════
DUMP_FILE="${BACKUP_DIR}/pathfinder_${TS}.dump"
log "Starting pg_dump -Fc ..."

docker exec "${CONTAINER}" \
    pg_dump -U "${PG_USER}" -d "${PG_DB}" -Fc \
    --no-owner --no-acl \
    -f "/tmp/pg_${TS}.dump" 2>&1 | while IFS= read -r line; do
    log "pg_dump: ${line}"
done

# Copy dump out of container
docker cp "${CONTAINER}:/tmp/pg_${TS}.dump" "${DUMP_FILE}"
docker exec "${CONTAINER}" rm "/tmp/pg_${TS}.dump"

DUMP_SIZE=$(stat --format=%s "${DUMP_FILE}" 2>/dev/null || echo 0)
log "pg_dump complete: ${DUMP_FILE} (${DUMP_SIZE} bytes)"

# ═══════════════════════════════════════════════════════════════════════
# V2: Schema-only dump (V2 verification: pg_restore --schema-only)
# ═══════════════════════════════════════════════════════════════════════
SCHEMA_FILE="${BACKUP_DIR}/pathfinder_${TS}_schema.sql"
log "Dumping schema-only ..."

docker exec "${CONTAINER}" \
    pg_dump -U "${PG_USER}" -d "${PG_DB}" --schema-only --no-owner --no-acl \
    -f "/tmp/schema_${TS}.sql" 2>&1 | while IFS= read -r line; do
    log "schema-dump: ${line}"
done

docker cp "${CONTAINER}:/tmp/schema_${TS}.sql" "${SCHEMA_FILE}"
docker exec "${CONTAINER}" rm "/tmp/schema_${TS}.sql"

SCHEMA_SIZE=$(stat --format=%s "${SCHEMA_FILE}" 2>/dev/null || echo 0)
log "Schema dump complete: ${SCHEMA_FILE} (${SCHEMA_SIZE} bytes)"

# ═══════════════════════════════════════════════════════════════════════
# V3: AGE catalog metadata (V3 verification: catalog count)
# ═══════════════════════════════════════════════════════════════════════
CATALOG_FILE="${BACKUP_DIR}/pathfinder_${TS}_catalog.json"
log "Extracting AGE catalog metadata ..."

docker exec "${CONTAINER}" bash -c "
    psql -U '${PG_USER}' -d '${PG_DB}' -c 'ANALYZE' > /dev/null 2>&1
    psql -U '${PG_USER}' -d '${PG_DB}' -t -A -q \
    -c \"SELECT json_build_object(
        'ts', now(),
        'db', current_database(),
        'tables', (SELECT json_agg(json_build_object('schema', schemaname, 'table', relname, 'rows', n_live_tup))
                   FROM pg_stat_user_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')),
        'total_rows', (SELECT sum(n_live_tup) FROM pg_stat_user_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')),
        'age_graphs', (SELECT json_agg(json_build_object('namespace', ag_graph.namespace::text, 'graph', ag_graph.name))
                       FROM ag_catalog.ag_graph),
        'age_labels', (SELECT json_agg(json_build_object('namespace', g.namespace::text, 'label', l.name, 'kind', l.kind::text))
                       FROM ag_catalog.ag_label l JOIN ag_catalog.ag_graph g ON g.graphid = l.graph),
        'age_vertex_count', (SELECT count(*) FROM ag_catalog.ag_label),
        'size_bytes', pg_database_size(current_database())
    )\" > /tmp/catalog_${TS}.json" 2>&1

docker cp "${CONTAINER}:/tmp/catalog_${TS}.json" "${CATALOG_FILE}"
docker exec "${CONTAINER}" rm "/tmp/catalog_${TS}.json"

log "Catalog metadata saved: ${CATALOG_FILE}"

# ═══════════════════════════════════════════════════════════════════════
# V1: sha256sum (file integrity)
# ═══════════════════════════════════════════════════════════════════════
CHECKSUM_FILE="${BACKUP_DIR}/checksums.sha256"
sha256sum "${DUMP_FILE}" "${SCHEMA_FILE}" "${CATALOG_FILE}" > "${CHECKSUM_FILE}"
log "Checksums written: ${CHECKSUM_FILE}"

# ═══════════════════════════════════════════════════════════════════════
# L3: Cloud sync (rclone → R2 / Wasabi / B2)
# 联合决议 (2026-05-20 v2): R2 主 (€0), Wasabi/B2 备选
# ═══════════════════════════════════════════════════════════════════════
RCLONE_REMOTE="${SCAILED_RCLONE_REMOTE:-r2}"
RCLONE_PATH="${SCAILED_RCLONE_PATH:-scailed-backups/pg}"

if command -v rclone &>/dev/null && rclone listremotes 2>/dev/null | grep -q "^${RCLONE_REMOTE}:"; then
    log "Syncing to ${RCLONE_REMOTE}:${RCLONE_PATH} ..."
    if rclone sync "${BACKUP_DIR}" "${RCLONE_REMOTE}:${RCLONE_PATH}/" \
        --checksum \
        --retries 3 \
        --low-level-retries 3 \
        --log-file="${BACKUP_ROOT}/rclone.log" \
        2>&1 | while IFS= read -r line; do
        log "rclone: ${line}"
    done; then
        log "Cloud sync OK: ${RCLONE_REMOTE}:${RCLONE_PATH}/"
    else
        log "WARN: Cloud sync FAILED (exit=$?). Local backup is safe. Check ${BACKUP_ROOT}/rclone.log"
    fi
else
    log "SKIP: rclone remote '${RCLONE_REMOTE}' not configured. Run deploy/setup-r2.sh to set up."
fi

# ═══════════════════════════════════════════════════════════════════════
# Cleanup: remove backups older than RETENTION_DAYS
# ═══════════════════════════════════════════════════════════════════════
DELETED=0
for dir in "${BACKUP_ROOT}"/*/; do
    dirname=$(basename "${dir}")
    # Skip non-timestamp dirs (e.g., logs)
    if [[ ! "${dirname}" =~ ^[0-9]{8}_[0-9]{6}$ ]]; then
        continue
    fi
    dir_ts=$(echo "${dirname}" | sed 's/_//')
    cutoff=$(date -d "-${RETENTION_DAYS} days" +%Y%m%d%H%M%S)
    if [[ "${dir_ts}" < "${cutoff}" ]]; then
        log "Purging old backup: ${dir}"
        rm -rf "${dir}"
        ((DELETED++)) || true
    fi
done
log "Retention cleanup: ${DELETED} old backup(s) removed (policy: ${RETENTION_DAYS} days)"

# ═══════════════════════════════════════════════════════════════════════
# Symlink: latest → current backup
# ═══════════════════════════════════════════════════════════════════════
ln -sfn "${TS}" "${BACKUP_ROOT}/latest"
log "Backup complete. latest → ${TS}"
log "=== DONE ==="
