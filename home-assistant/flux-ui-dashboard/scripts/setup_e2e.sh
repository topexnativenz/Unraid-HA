#!/usr/bin/env bash
# End-to-end Flux UI setup: assets → build → verify → deploy to HA.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/.."

echo "==> Installing Python deps"
python3 -m pip install -q -r "$ROOT/requirements.txt"

echo "==> Downloading bundled Mushroom + card-mod JS"
python3 "$ROOT/scripts/install_frontend_assets.py"

echo "==> Building Flux UI config"
GIT_BRANCH="$(git -C "$(dirname "$ROOT")/.." branch --show-current 2>/dev/null || true)"
GIT_HEAD="$(git -C "$(dirname "$ROOT")/.." rev-parse --short HEAD 2>/dev/null || true)"
echo "    Branch: ${GIT_BRANCH:-unknown} @ ${GIT_HEAD:-unknown}"
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

  # 16:9 tablet dashboard is the default for the wall-tablet HA user.
  # Display name in HA is typically "SmartHome Display 1" (alias: smarthome).
  TABLET_DEFAULT_USER="${TABLET_DEFAULT_USER:-SmartHome Display 1}"
  echo "==> Setting default dashboard for HA user '${TABLET_DEFAULT_USER}' → flux-ui-tablet"
  python3 "$ROOT/scripts/set_default_dashboard.py" \
    --user "$TABLET_DEFAULT_USER" --dashboard flux-ui-tablet \
    || echo "Warning: could not set default dashboard for '${TABLET_DEFAULT_USER}' (see above)."
fi

echo ""
echo "Done. Open: ${HA_URL:-http://192.168.1.239:8123}/flux-ui/overview"
echo "16:9 tablet: ${HA_URL:-http://192.168.1.239:8123}/flux-ui-tablet/overview"
