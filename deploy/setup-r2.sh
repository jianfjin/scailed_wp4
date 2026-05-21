#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# SCAILED WP4 — rclone R2 Setup
# 联合决议 (2026-05-20 v2): Cloudflare R2 主方案 (€0/10GB 免费)
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

REMOTE_NAME="${SCAILED_RCLONE_REMOTE:-r2}"

echo "=== SCAILED R2 rclone setup ==="
echo ""

# ─── Check rclone is installed ────────────────────────────────────────
if ! command -v rclone &>/dev/null; then
    echo "FATAL: rclone not found. Install: sudo apt-get install rclone"
    exit 1
fi

# ─── Gather credentials ────────────────────────────────────────────────
# Accept from args or prompt
ACCOUNT_ID="${1:-}"
ACCESS_KEY="${2:-}"
SECRET_KEY="${3:-}"

if [[ -z "${ACCOUNT_ID}" ]]; then
    read -rp "Cloudflare Account ID (dashboard → right sidebar): " ACCOUNT_ID
fi
if [[ -z "${ACCESS_KEY}" ]]; then
    read -rp "R2 Access Key ID: " ACCESS_KEY
fi
if [[ -z "${SECRET_KEY}" ]]; then
    read -rsp "R2 Secret Access Key: " SECRET_KEY
    echo ""
fi

if [[ -z "${ACCOUNT_ID}" || -z "${ACCESS_KEY}" || -z "${SECRET_KEY}" ]]; then
    echo "FATAL: All three fields required."
    exit 1
fi

# ─── Remove existing remote if present ─────────────────────────────────
if rclone listremotes 2>/dev/null | grep -q "^${REMOTE_NAME}:"; then
    echo "Remote '${REMOTE_NAME}' already exists. Replacing..."
    rclone config delete "${REMOTE_NAME}" 2>/dev/null || true
fi

# ─── Configure rclone ──────────────────────────────────────────────────
ENDPOINT="https://${ACCOUNT_ID}.r2.cloudflarestorage.com"

rclone config create "${REMOTE_NAME}" s3 \
    provider    Cloudflare \
    endpoint    "${ENDPOINT}" \
    access_key_id "${ACCESS_KEY}" \
    secret_access_key "${SECRET_KEY}" \
    region      auto \
    no_check_bucket true

echo ""
echo "Remote '${REMOTE_NAME}' configured."
echo "Endpoint: ${ENDPOINT}"

# ─── Verify ────────────────────────────────────────────────────────────
echo ""
echo "Testing connection..."

if rclone lsd "${REMOTE_NAME}:" 2>&1; then
    echo ""
    echo "=== SUCCESS ==="
    echo "Remote '${REMOTE_NAME}' is ready."
    echo ""
    echo "Next steps:"
    echo "  1. Create bucket in Cloudflare dashboard: scailed-backups"
    echo "  2. Run: rclone mkdir ${REMOTE_NAME}:scailed-backups/pg"
    echo "  3. Test sync: rclone sync /backups/pg/latest ${REMOTE_NAME}:scailed-backups/pg/"
    echo "  4. The backup cron will auto-sync from now on."
else
    echo ""
    echo "WARN: Connection test failed. Check credentials and try again."
    echo "  Endpoint: ${ENDPOINT}"
    exit 1
fi
