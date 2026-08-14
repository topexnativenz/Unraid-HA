#!/usr/bin/env bash
# Pull latest MD3 Flux UI code and deploy to HA.
#
# IMPORTANT: never pass a commit SHA as a second argument to `git reset --hard`.
# That is interpreted as a pathspec and fails with:
#   fatal: Cannot do hard reset with paths.
# The previous deploy then continues from the OLD SHA (e.g. fffb9cc instead of
# e89c8e2), so tablet LED package + newer layout never reach HA.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BRANCH="${FLUX_UI_BRANCH:-cursor/flux-ui-md3-dashboard-bf3a}"
ROOT="$REPO_ROOT/home-assistant/flux-ui-dashboard"

cd "$REPO_ROOT"

echo "==> Repo: $REPO_ROOT"
echo "==> Branch: $BRANCH"

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "==> Stashing local changes (restore later with: git stash pop)"
  git stash push -m "flux-ui update $(date +%Y%m%d-%H%M%S)"
fi

echo "==> Fetching + hard-resetting to origin/${BRANCH}"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
# Single argument only — do NOT append a SHA after the ref.
git reset --hard "origin/$BRANCH"

HEAD="$(git rev-parse --short HEAD)"
echo "==> Now on ${BRANCH} @ ${HEAD}"

if [[ ! -f "$ROOT/packages/flux_ui_tablet_led.yaml" ]]; then
  echo "ERROR: packages/flux_ui_tablet_led.yaml missing after reset — wrong SHA?"
  exit 1
fi

STILL_COUNT="$(find "$ROOT/www/flux-ui/camera-stills" -maxdepth 1 -name '*.webp' 2>/dev/null | wc -l | tr -d ' ')"
if [[ "${STILL_COUNT}" -lt 4 ]]; then
  echo "ERROR: expected branded camera still WebPs under www/flux-ui/camera-stills/ (found ${STILL_COUNT})."
  echo "  This branch/SHA is missing the animated stills merge."
  echo "  Use: FLUX_UI_BRANCH=cursor/flux-ui-md3-dashboard-bf3a (after stills merged) or cursor/camera-animated-stills-bf3a"
  exit 1
fi
echo "==> Camera stills: ${STILL_COUNT} branded WebP(s) ready"

echo "==> Deploying Flux UI from ${HEAD}"
bash "$ROOT/scripts/setup_e2e.sh" "$@"

echo ""
echo "Deployed ${BRANCH} @ ${HEAD}"
echo "Open: ${HA_URL:-http://192.168.1.239:8123}/flux-ui/overview"
echo "16:9: ${HA_URL:-http://192.168.1.239:8123}/flux-ui-tablet/overview"
echo "Expect: storage-mode tablet restored via lovelace/config/save (not YAML-only)."
echo "Tablet layout is LOCKED (gaps/spacings/sizings) — refresh/redeploy keep the same baseline YAML."
echo "If UI looks stale, hard-refresh (Cmd+Shift+R) or reset HA app cache."
echo "If configuration.yaml still had flux-ui-tablet YAML mode, deploy strips it — restart HA once if the sidebar entry is wrong."
