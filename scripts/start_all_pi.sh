#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

cd "$ROOT_DIR"
ensure_run_dir
PYTHON_BIN="$(python_bin)"

echo "[start_all_pi] stopping stale processes first"
bash "$ROOT_DIR/scripts/stop_all_pi.sh"

echo "[start_all_pi] launching runtime in background"
nohup "$PYTHON_BIN" -m pi.runtime.main > "$ROOT_DIR/.run/runtime.log" 2>&1 &
echo $! > "$ROOT_DIR/.run/runtime.pid"

sleep 2

echo "[start_all_pi] launching observer server in background"
nohup "$PYTHON_BIN" -m pi.server.app > "$ROOT_DIR/.run/server.log" 2>&1 &
echo $! > "$ROOT_DIR/.run/server.pid"

echo "[start_all_pi] done"
echo "Python:      $PYTHON_BIN"
echo "Runtime log: $ROOT_DIR/.run/runtime.log"
echo "Server log:  $ROOT_DIR/.run/server.log"
