#!/bin/bash
# Light inbound queue heal on tower (failed/stuck → auto reprocess). Safe daytime cron.
set -euo pipefail

REPO_ROOT="/Users/topexnative/Projects/unraid-array-design"
CONTAINER="${XERO_INBOUND_CONTAINER:-xero-inbound}"
LIMIT="${XERO_INBOUND_HEAL_LIMIT:-10}"
DRY_RUN="${XERO_INBOUND_HEAL_DRY_RUN:-}"

echo "Tower connectivity:"
"${REPO_ROOT}/tower/scripts/tower-resolve-host.sh" --json

ARGS=(python -m xero_mcp inbound heal --limit "${LIMIT}" --json)
if [[ -n "${DRY_RUN}" ]]; then
  ARGS+=(--dry-run)
fi

ssh -o ConnectTimeout=15 -o IdentitiesOnly=yes tower \
  "docker exec ${CONTAINER} ${ARGS[*]}"
