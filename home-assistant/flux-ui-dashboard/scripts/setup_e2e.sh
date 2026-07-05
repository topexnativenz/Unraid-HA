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
GIT_ROOT="$(cd "$ROOT/../.." && pwd)"
GIT_BRANCH="$(git -C "$GIT_ROOT" branch --show-current 2>/dev/null || true)"
GIT_HEAD="$(git -C "$GIT_ROOT" rev-parse --short HEAD 2>/dev/null || true)"
echo "    Branch: ${GIT_BRANCH:-unknown} @ ${GIT_HEAD:-unknown}"

if [[ ! -f "$ROOT/packages/flux_ui_rooms.yaml" ]]; then
  echo ""
  echo "ERROR: Missing packages/flux_ui_rooms.yaml — git pull may have failed."
  echo "  Run: git pull --rebase --autostash && bash home-assistant/scripts/run_all_e2e.sh"
  exit 1
fi

python3 "$ROOT/scripts/build_flux_ui.py" \
  --output "$ROOT/generated/lovelace.flux_ui.json"

echo "==> Verifying build"
python3 "$ROOT/scripts/verify_flux_ui.py"

echo "==> Deploying to Home Assistant"
if python3 "$ROOT/scripts/check_ha_credentials.py" >/dev/null 2>&1; then
  DEPLOY_ARGS=()
  if [[ -n "${HA_URL:-}" ]]; then
    DEPLOY_ARGS+=(--ha-url "$HA_URL")
  fi
  if [[ -n "${HA_TOKEN:-}" ]]; then
    DEPLOY_ARGS+=(--token "$HA_TOKEN")
  fi
  if ((${#DEPLOY_ARGS[@]})); then
    if (($#)); then
      python3 "$ROOT/scripts/deploy_flux_ui.py" "${DEPLOY_ARGS[@]}" "$@"
    else
      python3 "$ROOT/scripts/deploy_flux_ui.py" "${DEPLOY_ARGS[@]}"
    fi
  else
    if (($#)); then
      python3 "$ROOT/scripts/deploy_flux_ui.py" "$@"
    else
      python3 "$ROOT/scripts/deploy_flux_ui.py"
    fi
  fi
else
  echo "No HA token found — build-only (set HA_TOKEN / .secrets/ha.env for live deploy)"
  if (($#)); then
    python3 "$ROOT/scripts/deploy_flux_ui.py" --offline-ok "$@"
  else
    python3 "$ROOT/scripts/deploy_flux_ui.py" --offline-ok
  fi
fi

echo ""
echo "Done. Open: ${HA_URL:-http://192.168.1.239:8123}/flux-ui/overview"
