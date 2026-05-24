#!/usr/bin/env bash
# ─── SCAILED WP4 Mock Services Runner ────────────────────────────────
# Starts WP2/WP3/WP8 mock REST services as background subprocesses.
# Kills all children on exit.
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PID_FILE="${XDG_RUNTIME_DIR:-/tmp}/scailed-mocks.pid"

PORTS=(8102 8103 8108)
NAMES=("wp2_stakeholders" "wp3_roadmap" "wp8_rules")

start() {
    # Kill any leftover from a previous start
    stop 2>/dev/null || true
    rm -f "$PID_FILE"

    pushd "$PROJECT_DIR" > /dev/null

    # Activate venv if it exists
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi

    PIDS=()
    for i in "${!PORTS[@]}"; do
        PORT="${PORTS[$i]}"
        NAME="${NAMES[$i]}"
        # Build a small runner inline
        python3 -c "
import sys
sys.path.insert(0, 'services/mock')
import ${NAME}
${NAME}.web.run_app(${NAME}.create_app(), host='0.0.0.0', port=${PORT})
" &
        PIDS+=($!)
        echo "Started $NAME on port $PORT (PID $!)"
    done

    popd > /dev/null

    # Write PIDs for status/stop
    printf "%s\n" "${PIDS[@]}" > "$PID_FILE"

    # Wait for all — if any die, kill the rest
    trap 'kill "${PIDS[@]}" 2>/dev/null; exit' SIGINT SIGTERM
    wait
}

stop() {
    if [ -f "$PID_FILE" ]; then
        readarray -t PIDS < "$PID_FILE"
        kill "${PIDS[@]}" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo "Stopped all mock services"
    fi
}

status() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Mock services: NOT RUNNING"
        return 1
    fi
    readarray -t PIDS < "$PID_FILE"
    ALIVE=0
    for PID in "${PIDS[@]}"; do
        if kill -0 "$PID" 2>/dev/null; then
            ALIVE=$((ALIVE + 1))
        fi
    done
    if [ "$ALIVE" -eq "${#PORTS[@]}" ]; then
        echo "Mock services: RUNNING (${PORTS[*]})"
        for PORT in "${PORTS[@]}"; do
            HEALTH=$(curl -sf "http://localhost:$PORT/health" 2>/dev/null || echo "down")
            echo "  :$PORT → $HEALTH"
        done
    else
        echo "Mock services: PARTIAL ($ALIVE/${#PORTS[@]} alive)"
        return 1
    fi
}

case "${1:-status}" in
    start)   start ;;
    stop)    stop  ;;
    restart) stop; sleep 1; start ;;
    status)  status ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
