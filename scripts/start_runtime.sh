#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

echo "[start_runtime] starting Pi runtime from $ROOT_DIR"
cd "$ROOT_DIR"
"$(python_bin)" -u -m pi.runtime.main
