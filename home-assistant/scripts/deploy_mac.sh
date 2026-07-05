#!/usr/bin/env bash
# Single Mac deploy script — git sync, full E2E, package helper verification.
#
# From repo root (unraid-array-design):
#   bash home-assistant/scripts/deploy_mac.sh
#
# First time / if Rooms tabs do not switch after deploy:
#   bash home-assistant/scripts/deploy_mac.sh --restart-ha
#
# Requires: HA token in ~/.cursor/mcp.json

set -euo pipefail

HA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
GIT_ROOT="$(cd "$HA_DIR/.." && pwd)"
cd "$GIT_ROOT"

# shellcheck source=deploy_git_helpers.sh
source "$(dirname "$0")/deploy_git_helpers.sh"

GARAGE_ENTITIES="$HA_DIR/garage-doors/entities.yaml"
GARAGE_LOCAL="$HA_DIR/garage-doors/entities.local.yaml"
RESTART_HA=false
DEPLOY_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --restart-ha) RESTART_HA=true ;;
    *) DEPLOY_ARGS+=("$arg") ;;
  esac
done

echo "=============================================="
echo " Flux UI + dashboards — Mac deploy (optional — cloud agents use deploy_cloud.sh)"
echo " Repo: $GIT_ROOT"
echo " HA:   ${HA_URL:-http://192.168.1.239:8123}"
echo "=============================================="

if ! git -C "$GIT_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: $GIT_ROOT is not a git repository."
  exit 1
fi

BRANCH="$(git -C "$GIT_ROOT" branch --show-current 2>/dev/null || true)"
if [[ -z "${BRANCH}" ]]; then
  echo "ERROR: Detached HEAD — checkout a branch first:"
  echo "  git checkout cursor/floating-music-player-bf3a"
  exit 1
fi

echo ""
echo "==> [1/4] Git sync ($BRANCH)"

if ! git -C "$GIT_ROOT" diff --quiet HEAD -- "$GARAGE_ENTITIES" 2>/dev/null; then
  echo "    Resetting stale garage-doors/entities.yaml (blocks pull)"
  git -C "$GIT_ROOT" checkout -- "$GARAGE_ENTITIES"
fi

reset_flux_deploy_generated_files "$GIT_ROOT" "$HA_DIR"

git -C "$GIT_ROOT" fetch origin "$BRANCH" 2>/dev/null || git -C "$GIT_ROOT" fetch origin
BEHIND="$(git -C "$GIT_ROOT" rev-list --count "HEAD..origin/${BRANCH}" 2>/dev/null || echo 0)"
if [[ "${BEHIND}" != "0" ]]; then
  echo "    Pulling ${BEHIND} commit(s)"
  if ! git -C "$GIT_ROOT" pull --rebase --autostash origin "$BRANCH"; then
    echo ""
    echo "ERROR: git pull failed — resetting deploy-generated files and retrying once"
    reset_flux_deploy_generated_files "$GIT_ROOT" "$HA_DIR"
    git -C "$GIT_ROOT" rebase --abort 2>/dev/null || true
    git -C "$GIT_ROOT" merge --abort 2>/dev/null || true
    git -C "$GIT_ROOT" pull --rebase origin "$BRANCH"
  fi
  # Autostash apply can leave conflict markers in generated files.
  reset_flux_deploy_generated_files "$GIT_ROOT" "$HA_DIR"
else
  echo "    Up to date"
fi
echo "    Commit: $(git -C "$GIT_ROOT" rev-parse --short HEAD) — $(git -C "$GIT_ROOT" log -1 --format=%s | head -c 60)"

if [[ ! -f "$HA_DIR/flux-ui-dashboard/packages/flux_ui_rooms.yaml" ]]; then
  echo "ERROR: Missing flux_ui_rooms.yaml — checkout cursor/floating-music-player-bf3a"
  exit 1
fi

echo ""
echo "==> [2/4] Full E2E deploy (Flux UI + Mobile Home + garage)"
if ((${#DEPLOY_ARGS[@]})); then
  bash "$HA_DIR/scripts/run_all_e2e.sh" "${DEPLOY_ARGS[@]}"
else
  bash "$HA_DIR/scripts/run_all_e2e.sh"
fi

echo ""
echo "==> [3/4] Verify HA package helpers (Rooms tabs, music player)"
ENSURE_ARGS=(--ha-url "${HA_URL:-http://192.168.1.239:8123}")
if [[ -n "${HA_TOKEN:-}" ]]; then
  ENSURE_ARGS+=(--token "$HA_TOKEN")
fi
if [[ "$RESTART_HA" == true ]]; then
  ENSURE_ARGS+=(--restart-ha)
fi
python3 "$HA_DIR/flux-ui-dashboard/scripts/ensure_packages_loaded.py" "${ENSURE_ARGS[@]}" || {
  if [[ "$RESTART_HA" != true ]]; then
    echo ""
    echo "TIP: If Rooms tabs still show old layout, run once:"
    echo "  bash home-assistant/scripts/deploy_mac.sh --restart-ha"
  fi
  exit 1
}

echo ""
echo "==> [4/4] Done"
echo "  Flux UI:  ${HA_URL:-http://192.168.1.239:8123}/flux-ui/overview"
echo "  Rooms:    ${HA_URL:-http://192.168.1.239:8123}/flux-ui/rooms"
echo ""
echo "Hard-refresh HA app (Cmd+Shift+R) or force-quit and reopen."
echo "Rooms success: Default / Others / Outdoor pills + tall 2-column cards."
