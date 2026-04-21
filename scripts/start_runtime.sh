#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[start_runtime] starting Pi runtime from $ROOT_DIR"
python3 -m pi.runtime.main

