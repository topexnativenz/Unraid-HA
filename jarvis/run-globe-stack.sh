#!/usr/bin/env bash
# Run JARVIS globe backend + static file server for the 3D UI.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Installing Python deps…"
pip install -q -r "$ROOT/backend/requirements.txt"

echo "Starting WebSocket server on ws://localhost:8765 …"
python3 "$ROOT/backend/jarvis_globe_server.py" &
WS_PID=$!

cleanup() {
  kill "$WS_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "Serving globe UI at http://localhost:8080/globe-interface/"
cd "$ROOT"
python3 -m http.server 8080
