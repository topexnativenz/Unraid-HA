#!/usr/bin/env bash
# Pull latest MD3 Flux UI code (stash local changes) and deploy to HA.
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

echo "==> Pulling latest MD3 dashboard code"
git pull origin "$BRANCH"

echo "==> Deploying Flux UI"
bash "$ROOT/scripts/setup_e2e.sh" "$@"

echo ""
echo "Open: ${HA_URL:-http://192.168.1.239:8123}/flux-ui/overview"
echo "Expect: greeting header, purple wallpaper, glass button-cards, bottom navbar."
echo "If you still see Mushroom lock cards, hard-refresh (Cmd+Shift+R) or reset HA app cache."
