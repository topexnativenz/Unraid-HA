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

for f in media_players.yaml packages/flux_ui_media.yaml www/flux-ui/carousel-sync.js; do
  if [[ -f "$ROOT/$f" ]] && grep -q '^<<<<<<< ' "$ROOT/$f" 2>/dev/null; then
    echo ""
    echo "ERROR: Git conflict markers in flux-ui-dashboard/$f"
    echo "  git checkout -- home-assistant/flux-ui-dashboard/$f"
    echo "  bash home-assistant/scripts/deploy_mac.sh"
    exit 1
  fi
done

echo "==> Discovering Sonos media players from HA (names + zones)"
DISCOVER_ARGS=()
if python3 "$ROOT/scripts/check_ha_credentials.py" >/dev/null 2>&1; then
  if [[ -n "${HA_URL:-}" ]]; then
    DISCOVER_ARGS+=(--ha-url "$HA_URL")
  fi
  if [[ -n "${HA_TOKEN:-}" ]]; then
    DISCOVER_ARGS+=(--token "$HA_TOKEN")
  fi
  if ((${#DISCOVER_ARGS[@]})); then
    if ! python3 "$ROOT/scripts/discover_sonos.py" "${DISCOVER_ARGS[@]}" --apply; then
      echo ""
      echo "WARNING: Sonos discovery failed or no speakers found — building with existing media_players.yaml"
    fi
  else
    if ! python3 "$ROOT/scripts/discover_sonos.py" --apply; then
      echo ""
      echo "WARNING: Sonos discovery failed or no speakers found — building with existing media_players.yaml"
    fi
  fi
  echo "==> Discovering NZ MetService weather entity"
  if ((${#DISCOVER_ARGS[@]})); then
    python3 "$ROOT/scripts/discover_weather.py" "${DISCOVER_ARGS[@]}" --apply || true
  else
    python3 "$ROOT/scripts/discover_weather.py" --apply || true
  fi
else
  echo "    No HA credentials — using committed media_players.yaml (set HA_TOKEN for live Sonos names)"
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
