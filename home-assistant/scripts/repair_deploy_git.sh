#!/usr/bin/env bash
# One-shot repair when git pull failed with autostash / unmerged Sonos config files.
#
# Usage (from repo root):
#   bash home-assistant/scripts/repair_deploy_git.sh
#   bash home-assistant/scripts/repair_deploy_git.sh && bash home-assistant/scripts/deploy_mac.sh --restart-ha

set -euo pipefail

HA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
GIT_ROOT="$(cd "$HA_DIR/.." && pwd)"
cd "$GIT_ROOT"

# shellcheck source=deploy_git_helpers.sh
source "$(dirname "$0")/deploy_git_helpers.sh"

BRANCH="$(git branch --show-current 2>/dev/null || true)"
if [[ -z "${BRANCH}" ]]; then
  echo "ERROR: Detached HEAD — checkout your feature branch first."
  exit 1
fi

echo "Repairing git state on branch: ${BRANCH}"
repair_deploy_git_state "$GIT_ROOT" "$BRANCH" "$HA_DIR"

# Drop autostash entries left by failed pull --autostash (safe; deploy regenerates files).
while git stash list | grep -q 'autostash'; do
  echo "    Dropping autostash"
  git stash drop 2>/dev/null || break
done

echo ""
echo "Git repair complete. Status:"
git status -sb
echo ""
echo "Next: git pull && bash home-assistant/scripts/deploy_mac.sh --restart-ha"
