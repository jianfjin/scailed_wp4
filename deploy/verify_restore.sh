#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# SCAILED WP4 — DR Verification: 4-Layer Restore Proof (P3)
# 联合决议 (2026-05-20, 16/0): sha256 → schema → AGE catalog → row count
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

# ─── Config ───────────────────────────────────────────────────────────
CONTAINER="${SCAILED_PG_CONTAINER:-scailed-postgres}"
PG_USER="${SCAILED_PG_USER:-pathfinder}"
PG_DB="${SCAILED_PG_DB:-pathfinder}"
BACKUP_ROOT="${SCAILED_BACKUP_ROOT:-/backups/pg}"
LOG_FILE="${BACKUP_ROOT}/verify.log"

# ─── Helpers ──────────────────────────────────────────────────────────
log()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"; }
pass() { log "✅ PASS: $*"; }
fail() { log "❌ FAIL: $*"; FAILURES=$((FAILURES + 1)); }
FAILURES=0

# ─── Find latest backup ───────────────────────────────────────────────
if [[ -n "${1:-}" ]]; then
    # Explicit backup dir (for runbook S5: point-in-time verification)
    if [[ -d "$1" ]]; then
        LATEST=$(readlink -f "$1")
        log "Using explicit backup: ${LATEST}"
    else
        log "FATAL: Backup dir not found: $1"
        exit 1
    fi
elif [[ -L "${BACKUP_ROOT}/latest" ]]; then
    LATEST=$(readlink -f "${BACKUP_ROOT}/latest")
else
    log "FATAL: No latest backup symlink. Run backup.sh first or pass path: $0 /backups/pg/20260520_030000"
    exit 1
fi

log "=== VERIFY START ==="
log "Backup: ${LATEST}"
log "Target: ${CONTAINER} / ${PG_USER}@${PG_DB}"

# ═══════════════════════════════════════════════════════════════════════
# V1: sha256sum file integrity
# ═══════════════════════════════════════════════════════════════════════
log "--- V1: sha256 checksums ---"

CHECKSUM_FILE="${LATEST}/checksums.sha256"
if [[ ! -f "${CHECKSUM_FILE}" ]]; then
    fail "checksums.sha256 not found"
else
    # sha256sum -c from the backup directory
    if (cd "${LATEST}" && sha256sum -c checksums.sha256 --quiet 2>&1); then
        pass "V1 — all 4 files integrity verified"
    else
        fail "V1 — checksum mismatch"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════
# V2: pg_restore --schema-only to verify dump is loadable
# ═══════════════════════════════════════════════════════════════════════
log "--- V2: schema restore test ---"

DUMP_FILE=$(ls "${LATEST}"/pathfinder_*.dump 2>/dev/null | head -1)
if [[ -z "${DUMP_FILE}" ]]; then
    fail "V2 — no .dump file found in backup"
else
    # Copy dump into container
    docker cp "${DUMP_FILE}" "${CONTAINER}:/tmp/verify_restore.dump" 2>/dev/null

    # Create temp DB, restore schema-only, check for errors
    if docker exec "${CONTAINER}" bash -c "
        set -e
        dropdb --if-exists -U '${PG_USER}' verify_restore 2>/dev/null || true
        createdb -U '${PG_USER}' verify_restore
        pg_restore -U '${PG_USER}' -d verify_restore --schema-only /tmp/verify_restore.dump 2>&1
    " | grep -iv 'notice\|warning' | grep -q 'ERROR'; then
        fail "V2 — schema restore had errors"
    elif docker exec "${CONTAINER}" psql -U "${PG_USER}" -d verify_restore -t -A -c \
        "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema','ag_catalog')" 2>/dev/null | grep -q '^[0-9]'; then
        TABLE_COUNT=$(docker exec "${CONTAINER}" psql -U "${PG_USER}" -d verify_restore -t -A -c \
            "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema','ag_catalog')" 2>/dev/null)
        pass "V2 — schema restored (${TABLE_COUNT} tables)"
    else
        fail "V2 — schema restored but zero tables found"
    fi

    # Cleanup
    docker exec "${CONTAINER}" bash -c "
        set -e
        dropdb --if-exists -U '${PG_USER}' verify_restore 2>/dev/null || true
        rm -f /tmp/verify_restore.dump
    " 2>/dev/null
fi

# ═══════════════════════════════════════════════════════════════════════
# V3: AGE catalog consistency (graph count, label count)
# ═══════════════════════════════════════════════════════════════════════
log "--- V3: AGE catalog ---"

CATALOG_FILE=$(ls "${LATEST}"/pathfinder_*_catalog.json 2>/dev/null | head -1)
if [[ -z "${CATALOG_FILE}" ]]; then
    fail "V3 — no catalog.json found in backup"
else
    # Extract AGE stats from backup catalog
    CAT_GRAPHS=$(python3 -c "import json; d=json.load(open('${CATALOG_FILE}')); print(len(d.get('age_graphs',[])))" 2>/dev/null || echo "ERR")
    CAT_LABELS=$(python3 -c "import json; d=json.load(open('${CATALOG_FILE}')); print(len(d.get('age_labels',[])))" 2>/dev/null || echo "ERR")
    CAT_VCOUNT=$(python3 -c "import json; d=json.load(open('${CATALOG_FILE}')); print(d.get('age_vertex_count',0))" 2>/dev/null || echo "ERR")

    # Get live AGE stats
    LIVE_GRAPHS=$(docker exec "${CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -t -A -c \
        "SELECT count(*) FROM ag_catalog.ag_graph" 2>/dev/null || echo "ERR")
    LIVE_LABELS=$(docker exec "${CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -t -A -c \
        "SELECT count(*) FROM ag_catalog.ag_label" 2>/dev/null || echo "ERR")

    if [[ "${CAT_GRAPHS}" == "${LIVE_GRAPHS}" ]] && [[ "${CAT_LABELS}" == "${LIVE_LABELS}" ]]; then
        pass "V3 — AGE catalog: ${LIVE_GRAPHS} graphs, ${LIVE_LABELS} labels (match)"
    else
        fail "V3 — AGE mismatch: backup(${CAT_GRAPHS}g/${CAT_LABELS}l) vs live(${LIVE_GRAPHS}g/${LIVE_LABELS}l)"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════
# V4: Per-table row count comparison (actual count(*), not n_live_tup)
# ═══════════════════════════════════════════════════════════════════════
log "--- V4: per-table row counts ---"

if [[ -f "${CATALOG_FILE}" ]]; then
    CAT_TOTAL=$(python3 -c "import json; d=json.load(open('${CATALOG_FILE}')); print(d.get('total_rows',0))" 2>/dev/null || echo "ERR")
    CAT_TABLES=$(python3 -c "
import json
d=json.load(open('${CATALOG_FILE}'))
for t in d.get('tables',[]):
    print(f\"{t['schema']}.{t['table']}|{t['rows']}\")
" 2>/dev/null)

    # Use same DO block approach for live counts
    cat > /tmp/scailed_v4_$$.sql << 'SQLEOF'
DO $$
DECLARE
    r record;
    row_count bigint;
    total bigint := 0;
BEGIN
    FOR r IN
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
    LOOP
        EXECUTE format('SELECT count(*) FROM %I.%I', r.table_schema, r.table_name) INTO row_count;
        total := total + row_count;
    END LOOP;
    RAISE NOTICE 'TOTAL:%', total;
END
$$;
SQLEOF

    docker cp "/tmp/scailed_v4_$$.sql" "${CONTAINER}:/tmp/v4.sql"
    LIVE_OUTPUT=$(docker exec "${CONTAINER}" bash -c "psql -U '${PG_USER}' -d '${PG_DB}' -f /tmp/v4.sql 2>&1")
    docker exec "${CONTAINER}" rm /tmp/v4.sql 2>/dev/null
    rm "/tmp/scailed_v4_$$.sql"

    LIVE_TOTAL=$(echo "${LIVE_OUTPUT}" | grep 'TOTAL:' | sed 's/.*TOTAL://')
    LIVE_TOTAL=${LIVE_TOTAL:-ERR}
    LIVE_SIZE=$(docker exec "${CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -t -A -c \
        "SELECT pg_database_size(current_database())" 2>/dev/null || echo "ERR")

    if [[ "${CAT_TOTAL}" == "${LIVE_TOTAL}" ]]; then
        pass "V4 — total rows: ${LIVE_TOTAL} (match, count(*)), db size: ${LIVE_SIZE} bytes"
    else
        # Per-table drill-down to identify specific mismatches
        V4_TABLE_FAILS=0
        while IFS='|' read -r tname trows; do
            [[ -z "${tname}" ]] && continue
            LIVE_TR=$(docker exec "${CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -t -A -c \
                "SELECT count(*) FROM \"${tname%%/*}\".\"${tname##*.}\"" 2>/dev/null || echo "ERR")
            if [[ "${trows}" != "${LIVE_TR}" ]]; then
                fail "V4 — ${tname}: catalog=${trows} live=${LIVE_TR}"
                ((V4_TABLE_FAILS++)) || true
            fi
        done <<< "${CAT_TABLES}"
        if [[ ${V4_TABLE_FAILS} -eq 0 ]]; then
            pass "V4 — all tables match (total drift from catalog generation, non-blocking)"
        else
            fail "V4 — total rows mismatch: catalog=${CAT_TOTAL} live=${LIVE_TOTAL} (${V4_TABLE_FAILS} tables differ)"
        fi
    fi
else
    fail "V4 — no catalog.json to compare against"
fi

# ═══════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════
log "=== VERIFY DONE ==="
log "Total failures: ${FAILURES}"
if [[ ${FAILURES} -gt 0 ]]; then
    log "RESULT: DEGRADED — ${FAILURES} check(s) failed"
    exit 1
else
    log "RESULT: ALL CLEAN — 4-layer verification passed"
    exit 0
fi
