#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
BRANCH="${1:-main}"

cd "$ROOT_DIR"

echo "[update_and_restart] repo: $ROOT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[update_and_restart] error: this folder is not a git repository"
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "[update_and_restart] error: working tree has local changes"
  echo "[update_and_restart] commit or stash them before pulling"
  git status --short
  exit 1
fi

echo "[update_and_restart] stopping running services"
bash "$ROOT_DIR/scripts/stop_all_pi.sh"

echo "[update_and_restart] fetching latest changes"
git fetch origin "$BRANCH"

LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git rev-parse "origin/$BRANCH")"

if [[ "$LOCAL_SHA" == "$REMOTE_SHA" ]]; then
  echo "[update_and_restart] already up to date on $BRANCH"
else
  echo "[update_and_restart] pulling origin/$BRANCH"
  git pull --ff-only origin "$BRANCH"
fi

echo "[update_and_restart] restarting services"
bash "$ROOT_DIR/scripts/start_all_pi.sh"

echo "[update_and_restart] complete"
