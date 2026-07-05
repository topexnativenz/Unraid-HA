#!/usr/bin/env bash
# Full E2E: Flux UI MD3 → Mobile Home → garage doors (optional sync).
# Cloud agents: bash home-assistant/scripts/deploy_cloud.sh  (or --cloud here)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
GIT_ROOT="$(cd "$REPO/.." && pwd)"
cd "$REPO"

# shellcheck source=deploy_git_helpers.sh
source "$(dirname "$0")/deploy_git_helpers.sh"

FLUX="$REPO/flux-ui-dashboard"
GARAGE="$REPO/garage-doors"
MOBILE="$REPO/mobile-dashboard"

CLOUD_MODE=false
EXTRA_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --cloud) CLOUD_MODE=true ;;
    *) EXTRA_ARGS+=("$arg") ;;
  esac
done

# Load repo secrets for cloud sessions.
if [[ -f "$GIT_ROOT/.secrets/ha.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$GIT_ROOT/.secrets/ha.env"
  set +a
fi

echo "=============================================="
echo " Home Assistant dashboards — full E2E deploy"
echo " Repo: $REPO"
echo " HA:   ${HA_URL:-http://192.168.1.239:8123}"
if [[ "$CLOUD_MODE" == true ]]; then
  echo " Mode: cloud (skip git sync — agent already pushed)"
fi
echo "=============================================="

# Keep repo current — autostash LAN-specific garage sensor mappings (entities.local.yaml).
if [[ "$CLOUD_MODE" != true ]] && git rev-parse --git-dir >/dev/null 2>&1; then
  BRANCH="$(git branch --show-current 2>/dev/null || true)"
  if [[ -n "${BRANCH}" ]]; then
    echo ""
    echo "==> Syncing git ($BRANCH)"
    reset_flux_deploy_generated_files "$GIT_ROOT" "$REPO"
    git fetch origin "$BRANCH" 2>/dev/null || git fetch origin 2>/dev/null || true
    BEHIND="$(git rev-list --count "HEAD..origin/${BRANCH}" 2>/dev/null || echo 0)"
    if [[ "${BEHIND}" != "0" ]]; then
      echo "    Branch is ${BEHIND} commit(s) behind origin/${BRANCH} — pulling with autostash"
      if ! git pull --rebase --autostash origin "$BRANCH"; then
        echo ""
        echo "ERROR: git pull failed — resetting deploy-generated files and retrying once"
        reset_flux_deploy_generated_files "$GIT_ROOT" "$REPO"
        git rebase --abort 2>/dev/null || true
        git merge --abort 2>/dev/null || true
        git pull --rebase origin "$BRANCH"
      fi
      reset_flux_deploy_generated_files "$GIT_ROOT" "$REPO"
    else
      echo "    Up to date with origin/${BRANCH}"
    fi
    echo "    Deploy commit: $(git rev-parse --short HEAD) ($(git log -1 --format=%s | head -c 60))"
  fi
fi

python3 -m pip install -q -r "$FLUX/requirements.txt"

echo ""
echo "==> [1/3] Flux UI MD3 (assets → build → verify → deploy)"
if ((${#EXTRA_ARGS[@]})); then
  bash "$FLUX/scripts/setup_e2e.sh" "${EXTRA_ARGS[@]}"
else
  bash "$FLUX/scripts/setup_e2e.sh"
fi

echo ""
echo "==> [2/3] Mobile Home (build + live push)"
if python3 "$FLUX/scripts/check_ha_credentials.py" >/dev/null 2>&1; then
  MOBILE_ARGS=(--ha-url "${HA_URL:-http://192.168.1.239:8123}")
  if [[ -n "${HA_TOKEN:-}" ]]; then
    MOBILE_ARGS+=(--token "$HA_TOKEN")
  fi
  if ((${#EXTRA_ARGS[@]})); then
    python3 "$MOBILE/scripts/deploy_mobile_home.py" "${MOBILE_ARGS[@]}" "${EXTRA_ARGS[@]}" \
      || echo "Warning: Mobile Home deploy failed (Flux UI may still be OK)."
  else
    python3 "$MOBILE/scripts/deploy_mobile_home.py" "${MOBILE_ARGS[@]}" \
      || echo "Warning: Mobile Home deploy failed (Flux UI may still be OK)."
  fi
else
  echo "No HA token — skipping Mobile Home live deploy."
fi

echo ""
echo "==> [3/3] Garage doors (package + Tapo sensor sync)"
GARAGE_ARGS=(--offline-ok --ha-url "${HA_URL:-http://192.168.1.239:8123}")
if [[ -n "${HA_TOKEN:-}" ]]; then
  GARAGE_ARGS+=(--token "$HA_TOKEN")
fi
if ((${#EXTRA_ARGS[@]})); then
  python3 "$GARAGE/scripts/deploy_garage_doors_pulse.py" "${GARAGE_ARGS[@]}" "${EXTRA_ARGS[@]}" || {
    echo "Warning: garage deploy/sync failed — update garage-doors/entities.local.yaml with real Tapo sensor IDs."
    echo "  python3 $GARAGE/scripts/list_garage_sensors.py"
  }
else
  python3 "$GARAGE/scripts/deploy_garage_doors_pulse.py" "${GARAGE_ARGS[@]}" || {
    echo "Warning: garage deploy/sync failed — update garage-doors/entities.local.yaml with real Tapo sensor IDs."
    echo "  python3 $GARAGE/scripts/list_garage_sensors.py"
  }
fi

echo ""
echo "=============================================="
echo " E2E complete"
echo "  Flux UI:    ${HA_URL:-http://192.168.1.239:8123}/flux-ui/overview"
echo "  Mobile:     ${HA_URL:-http://192.168.1.239:8123}/mobile-home/home"
echo "=============================================="
echo "Flux MD3 check: deploy log above must show:"
echo "  - rooms: copied packages/flux_ui_rooms.yaml + input_select.flux_ui_rooms_tab loaded"
echo "  - overview sections=5 (with music player) or sections=4 (without)"
echo "Hard-refresh browser after deploy (Cmd+Shift+R)."
