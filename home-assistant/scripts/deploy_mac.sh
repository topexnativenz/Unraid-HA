#!/usr/bin/env bash
# Mac one-command deploy — fixes common git pull blockers, then runs full E2E.
#
# Usage (from anywhere):
#   bash home-assistant/scripts/deploy_mac.sh
#
# Or from repo root:
#   bash home-assistant/scripts/deploy_mac.sh
#
# Requires: HA token in ~/.cursor/mcp.json (same as other deploy scripts)

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

GARAGE_ENTITIES="$REPO/garage-doors/entities.yaml"
GARAGE_LOCAL="$REPO/garage-doors/entities.local.yaml"
GARAGE_EXAMPLE="$REPO/garage-doors/entities.local.yaml.example"

echo "=============================================="
echo " Mac deploy — Unraid-HA dashboards"
echo " Repo: $REPO"
echo " HA:   ${HA_URL:-http://192.168.1.239:8123}"
echo "=============================================="

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: Not a git repository."
  exit 1
fi

BRANCH="$(git branch --show-current 2>/dev/null || true)"
if [[ -z "${BRANCH}" ]]; then
  echo "ERROR: Detached HEAD — checkout a branch first, e.g.:"
  echo "  git checkout cursor/flux-ui-md3-dashboard-bf3a"
  exit 1
fi

echo ""
echo "==> Preparing git ($BRANCH)"

# Old deploys wrote Tapo sensor IDs into tracked entities.yaml — that blocks git pull.
# Preserve LAN mappings in gitignored entities.local.yaml, then reset entities.yaml.
if git diff --quiet HEAD -- "$GARAGE_ENTITIES" 2>/dev/null; then
  : # clean
elif [[ -f "$GARAGE_ENTITIES" ]]; then
  echo "    Local edits detected in garage-doors/entities.yaml (blocks git pull)"
  if [[ ! -f "$GARAGE_LOCAL" ]] && command -v python3 >/dev/null 2>&1; then
    python3 - <<PY || true
import yaml
from pathlib import Path

repo = Path(${REPO@Q})
entities = repo / "garage-doors/entities.yaml"
local = repo / "garage-doors/entities.local.yaml"
if not entities.exists():
    raise SystemExit(0)
data = yaml.safe_load(entities.read_text()) or {}
doors = data.get("doors", [])
if not doors:
    raise SystemExit(0)
header = (
    "# Auto-migrated from local entities.yaml edits (gitignored).\n"
    "# Re-run discover after adding Tapo sensors:\n"
    "#   python3 home-assistant/garage-doors/scripts/discover_garage_doors.py --apply\n\n"
)
local.write_text(header + yaml.safe_dump({"doors": doors}, sort_keys=False, default_flow_style=False))
print(f"    Saved sensor mappings → {local}")
PY
  fi
  if [[ ! -f "$GARAGE_LOCAL" ]] && [[ -f "$GARAGE_EXAMPLE" ]]; then
    echo "    Tip: copy entities.local.yaml.example after pull if garage icons need your Tapo IDs"
  fi
  echo "    Resetting garage-doors/entities.yaml to repo version"
  git checkout -- "$GARAGE_ENTITIES"
fi

# Stash any other local changes, pull, restore stash.
echo "    Fetching origin/$BRANCH"
git fetch origin "$BRANCH" 2>/dev/null || git fetch origin

BEHIND="$(git rev-list --count "HEAD..origin/${BRANCH}" 2>/dev/null || echo 0)"
if [[ "${BEHIND}" != "0" ]]; then
  echo "    Pulling ${BEHIND} commit(s) with autostash"
  if ! git pull --rebase --autostash origin "$BRANCH"; then
    echo ""
    echo "ERROR: git pull failed."
    echo "  Try: git status"
    echo "  Then fix conflicts or: git merge --abort / git rebase --abort"
    exit 1
  fi
else
  echo "    Already up to date with origin/$BRANCH"
fi

COMMIT="$(git rev-parse --short HEAD)"
MSG="$(git log -1 --format=%s | head -c 72)"
echo "    Deploy commit: $COMMIT — $MSG"

if [[ ! -f "$REPO/flux-ui-dashboard/packages/flux_ui_rooms.yaml" ]]; then
  echo ""
  echo "ERROR: flux_ui_rooms.yaml missing — Rooms ElementZoom layout not in this commit."
  echo "  Try: git checkout cursor/floating-music-player-bf3a"
  echo "    or: git pull origin cursor/floating-music-player-bf3a"
  exit 1
fi

echo ""
echo "==> Running full E2E deploy"
bash "$REPO/scripts/run_all_e2e.sh" "$@"
