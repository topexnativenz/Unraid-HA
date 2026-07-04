#!/usr/bin/env bash
# Full E2E: garage doors → Flux UI MD3 → Mobile Home.
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

python3 -m pip install -q -r "$FLUX/requirements.txt"

echo ""
echo "==> [1/3] Garage doors (package + Tapo sensor sync)"
python3 "$GARAGE/scripts/deploy_garage_doors_pulse.py" --offline-ok "$@"

echo ""
echo "==> [2/3] Flux UI MD3 (assets → build → verify → deploy)"
bash "$FLUX/scripts/setup_e2e.sh" "$@"

echo ""
echo "==> [3/3] Mobile Home (build + live push)"
if [[ -z "${HA_TOKEN:-}" ]] && [[ ! -f "${HOME}/.cursor/mcp.json" ]] && [[ ! -f "/Users/topexnative/.cursor/mcp.json" ]]; then
  echo "No HA token — skipping Mobile Home live deploy."
else
  python3 "$MOBILE/scripts/deploy_mobile_home.py" "$@"
fi

echo ""
echo "=============================================="
echo " E2E complete"
echo "  Flux UI:    ${HA_URL:-http://192.168.1.239:8123}/flux-ui/overview"
echo "  Mobile:     ${HA_URL:-http://192.168.1.239:8123}/mobile-home/home"
echo "=============================================="
echo "Flux MD3 check: deploy log must show sections=5"
echo "Hard-refresh browser after deploy (Cmd+Shift+R)."
