#!/usr/bin/env bash
set -euo pipefail

echo "[stop_all_pi] stopping runtime, server, and camera helpers"
pkill -f "pi.runtime.main" || true
pkill -f "pi.server.app" || true
pkill -f "rpicam-vid" || true
