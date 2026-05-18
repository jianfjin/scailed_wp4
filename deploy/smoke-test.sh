#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# SCAILED Pathfinder — Post-Deploy Smoke Test Wrapper
#
# Usage: bash deploy/smoke-test.sh
#
# This wrapper runs the Python smoke_test.py script from the same directory.
# All arguments are forwarded to the Python script.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SMOKE_PY="${SCRIPT_DIR}/smoke_test.py"

if [ ! -f "$SMOKE_PY" ]; then
    echo "ERROR: smoke_test.py not found at ${SMOKE_PY}" >&2
    exit 1
fi

echo "=== SCAILED Smoke Test Wrapper ==="
echo "Script : ${SMOKE_PY}"
echo ""

exec python3 "${SMOKE_PY}" "$@"
