#!/usr/bin/env bash
set -euo pipefail

echo "[stop_all_pi] stopping runtime, server, and camera helpers"
pkill -f "python3 -m pi.runtime.main" || true
pkill -f "python3 -m pi.server.app" || true
pkill -f "rpicam-vid" || true

