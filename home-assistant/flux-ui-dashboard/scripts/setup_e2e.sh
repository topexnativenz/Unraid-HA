#!/usr/bin/env bash
# End-to-end Flux UI setup: assets → build → verify → deploy to HA.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/.."

echo "==> Installing Python deps"
pip install -q -r "$ROOT/requirements.txt"

echo "==> Downloading bundled Mushroom + card-mod JS"
python3 "$ROOT/scripts/install_frontend_assets.py"

echo "==> Building Flux UI config"
python3 "$ROOT/scripts/build_flux_ui.py" \
  --output "$ROOT/generated/lovelace.flux_ui.json"

echo "==> Verifying build"
python3 "$ROOT/scripts/verify_flux_ui.py"

echo "==> Deploying to Home Assistant"
if [[ -z "${HA_TOKEN:-}" ]] && [[ ! -f "${HOME}/.cursor/mcp.json" ]] && [[ ! -f "/Users/topexnative/.cursor/mcp.json" ]]; then
  echo "No HA token found — build-only (pass HA_TOKEN or run on Mac with mcp.json for live deploy)"
  python3 "$ROOT/scripts/deploy_flux_ui.py" --offline-ok "$@"
else
  python3 "$ROOT/scripts/deploy_flux_ui.py" "$@"
fi

echo ""
echo "Done. Open: ${HA_URL:-http://192.168.1.239:8123}/flux-ui/overview"
