#!/usr/bin/env bash
# Full E2E: Flux UI MD3 → Mobile Home → garage doors (optional sync).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

FLUX="$REPO/flux-ui-dashboard"
GARAGE="$REPO/garage-doors"
MOBILE="$REPO/mobile-dashboard"

echo "=============================================="
echo " Home Assistant dashboards — full E2E deploy"
echo " Repo: $REPO"
echo " HA:   ${HA_URL:-http://192.168.1.239:8123}"
echo "=============================================="

# Keep repo current — autostash LAN-specific garage sensor mappings (entities.local.yaml).
if git rev-parse --git-dir >/dev/null 2>&1; then
  BRANCH="$(git branch --show-current 2>/dev/null || true)"
  if [[ -n "${BRANCH}" ]]; then
    echo ""
    echo "==> Syncing git ($BRANCH)"
    git fetch origin "$BRANCH" 2>/dev/null || git fetch origin 2>/dev/null || true
    BEHIND="$(git rev-list --count "HEAD..origin/${BRANCH}" 2>/dev/null || echo 0)"
    if [[ "${BEHIND}" != "0" ]]; then
      echo "    Branch is ${BEHIND} commit(s) behind origin/${BRANCH} — pulling with autostash"
      if ! git pull --rebase --autostash origin "$BRANCH"; then
        echo ""
        echo "ERROR: git pull failed — fix conflicts, then re-run E2E."
        echo "  If garage-doors/entities.yaml has local edits from an old deploy, run:"
        echo "    git checkout -- home-assistant/garage-doors/entities.yaml"
        echo "    git pull --rebase --autostash"
        exit 1
      fi
    else
      echo "    Up to date with origin/${BRANCH}"
    fi
    echo "    Deploy commit: $(git rev-parse --short HEAD) ($(git log -1 --format=%s | head -c 60))"
  fi
fi

python3 -m pip install -q -r "$FLUX/requirements.txt"

echo ""
echo "==> [1/3] Flux UI MD3 (assets → build → verify → deploy)"
bash "$FLUX/scripts/setup_e2e.sh" "$@"

echo ""
echo "==> [2/3] Mobile Home (build + live push)"
if [[ -z "${HA_TOKEN:-}" ]] && [[ ! -f "${HOME}/.cursor/mcp.json" ]] && [[ ! -f "/Users/topexnative/.cursor/mcp.json" ]]; then
  echo "No HA token — skipping Mobile Home live deploy."
else
  python3 "$MOBILE/scripts/deploy_mobile_home.py" "$@" || echo "Warning: Mobile Home deploy failed (Flux UI may still be OK)."
fi

echo ""
echo "==> [3/3] Garage doors (package + Tapo sensor sync)"
python3 "$GARAGE/scripts/deploy_garage_doors_pulse.py" --offline-ok "$@" || {
  echo "Warning: garage deploy/sync failed — update garage-doors/entities.local.yaml with real Tapo sensor IDs."
  echo "  python3 $GARAGE/scripts/list_garage_sensors.py"
}

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
