#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

echo "[start_server] starting observer server from $ROOT_DIR"
cd "$ROOT_DIR"
"$(python_bin)" -m pi.server.app
