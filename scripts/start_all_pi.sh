#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p "$ROOT_DIR/.run"

echo "[start_all_pi] stopping stale processes first"
"$ROOT_DIR/scripts/stop_all_pi.sh"

echo "[start_all_pi] launching runtime in background"
nohup python3 -m pi.runtime.main > "$ROOT_DIR/.run/runtime.log" 2>&1 &
echo $! > "$ROOT_DIR/.run/runtime.pid"

sleep 2

echo "[start_all_pi] launching observer server in background"
nohup python3 -m pi.server.app > "$ROOT_DIR/.run/server.log" 2>&1 &
echo $! > "$ROOT_DIR/.run/server.pid"

echo "[start_all_pi] done"
echo "Runtime log: $ROOT_DIR/.run/runtime.log"
echo "Server log:  $ROOT_DIR/.run/server.log"
