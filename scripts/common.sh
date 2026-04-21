#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python_bin() {
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    echo "$ROOT_DIR/.venv/bin/python"
  else
    echo "python3"
  fi
}

ensure_run_dir() {
  mkdir -p "$ROOT_DIR/.run"
}
