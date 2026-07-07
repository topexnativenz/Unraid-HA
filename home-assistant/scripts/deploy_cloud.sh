#!/usr/bin/env bash
# Cloud agent E2E deploy — runs automatically at the end of every Cursor agent task.
# No Mac required. Agent commits/pushes code; this script builds and deploys to live HA.
#
# Requires (Cursor Cloud Agent secrets or .secrets/ha.env):
#   HA_URL   — e.g. https://xxxx.ui.nabu.casa or http://192.168.1.239:8123
#   HA_TOKEN — long-lived access token
#
# Optional (package push when cloud cannot reach LAN SMB):
#   HA_HOST        — LAN or Tailscale IP for Samba (default 192.168.1.239)
#   HA_SSH_HOST    — Tailscale / SSH add-on host for scp package sync
#   HA_SSH_USER    — SSH username
#   HA_SSH_KEY_PATH — path to private key (recommended)
#
# Usage (agents — do not ask the user to run this):
#   bash home-assistant/scripts/deploy_cloud.sh
#
# First-time package helper load:
#   bash home-assistant/scripts/deploy_cloud.sh --restart-ha

set -euo pipefail

HA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
GIT_ROOT="$(cd "$HA_DIR/.." && pwd)"
cd "$GIT_ROOT"

RESTART_HA=false
DEPLOY_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --restart-ha) RESTART_HA=true ;;
    *) DEPLOY_ARGS+=("$arg") ;;
  esac
done

# Load repo secrets (gitignored) — Cursor env vars take precedence.
if [[ -f "$GIT_ROOT/.secrets/ha.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$GIT_ROOT/.secrets/ha.env"
  set +a
fi

HA_URL="${HA_URL:-http://192.168.1.239:8123}"

echo "=============================================="
echo " Flux UI — Cloud agent E2E deploy"
echo " Repo: $GIT_ROOT"
echo " HA:   $HA_URL"
echo " Branch: $(git branch --show-current 2>/dev/null || echo unknown)"
echo " Commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "=============================================="

echo ""
echo "==> [1/5] Verify HA credentials"
if ! python3 "$HA_DIR/flux-ui-dashboard/scripts/check_ha_credentials.py"; then
  echo ""
  echo "ERROR: HA credentials missing."
  echo "  Add HA_URL + HA_TOKEN to Cursor Cloud Agent secrets, or create:"
  echo "    $GIT_ROOT/.secrets/ha.env"
  echo "  See .secrets/ha.env.example"
  exit 1
fi

echo ""
echo "==> [2/5] Build + live deploy (Flux UI + Mobile Home + garage)"
if ((${#DEPLOY_ARGS[@]})); then
  bash "$HA_DIR/scripts/run_all_e2e.sh" --cloud "${DEPLOY_ARGS[@]}"
else
  bash "$HA_DIR/scripts/run_all_e2e.sh" --cloud
fi

echo ""
echo "==> [3/5] Push packages / www / themes (SMB or SSH fallback)"
PUSH_ARGS=(--ha-url "$HA_URL")
if [[ -n "${HA_TOKEN:-}" ]]; then
  PUSH_ARGS+=(--token "$HA_TOKEN")
fi
python3 "$HA_DIR/flux-ui-dashboard/scripts/push_ha_files.py" "${PUSH_ARGS[@]}" || {
  echo "  (package push skipped — Lovelace API deploy may still have succeeded)"
}

echo ""
echo "==> [4/5] Verify HA package helpers (Rooms tabs, music player)"
ENSURE_ARGS=(--ha-url "$HA_URL")
if [[ -n "${HA_TOKEN:-}" ]]; then
  ENSURE_ARGS+=(--token "$HA_TOKEN")
fi
if [[ "$RESTART_HA" == true ]]; then
  ENSURE_ARGS+=(--restart-ha)
fi
python3 "$HA_DIR/flux-ui-dashboard/scripts/ensure_packages_loaded.py" "${ENSURE_ARGS[@]}" || {
  if [[ "$RESTART_HA" != true ]]; then
    echo ""
    echo "TIP: If Rooms tabs still show old layout, re-run with:"
    echo "  bash home-assistant/scripts/deploy_cloud.sh --restart-ha"
  fi
  exit 1
}

echo ""
echo "==> [5/5] Live verification"
VERIFY_ARGS=(--live --ha-url "$HA_URL")
if [[ -n "${HA_TOKEN:-}" ]]; then
  VERIFY_ARGS+=(--token "$HA_TOKEN")
fi
python3 "$HA_DIR/flux-ui-dashboard/scripts/verify_flux_ui.py" "${VERIFY_ARGS[@]}"

echo ""
echo "=============================================="
echo " Cloud E2E deploy complete"
echo "  Flux UI:  ${HA_URL}/flux-ui/overview"
echo "  Rooms:    ${HA_URL}/flux-ui/rooms"
echo "  Mobile:   ${HA_URL}/mobile-home/home"
echo "=============================================="
echo "Hard-refresh HA app or Reset Frontend Cache on iOS Companion."
