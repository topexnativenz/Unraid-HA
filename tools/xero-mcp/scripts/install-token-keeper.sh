#!/bin/bash
# Install launchd agent: refreshes Xero OAuth token every 15 min (hands-off).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="${REPO_ROOT}/.venv/bin/python"
LABEL="com.unraid-array-design.xero-mcp-token-keeper"
PLIST_DEST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="${HOME}/.config/xero-mcp"
TEMPLATE="${REPO_ROOT}/scripts/com.unraid-array-design.xero-mcp-token-keeper.plist.template"

mkdir -p "${LOG_DIR}" "${HOME}/Library/LaunchAgents"
chmod 700 "${LOG_DIR}"

sed \
  -e "s|__VENV_PY__|${VENV_PY}|g" \
  -e "s|__LOG_DIR__|${LOG_DIR}|g" \
  "${TEMPLATE}" > "${PLIST_DEST}"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${PLIST_DEST}"
launchctl enable "gui/$(id -u)/${LABEL}" 2>/dev/null || true

echo "Installed token keeper: ${PLIST_DEST}"
echo "Logs: ${LOG_DIR}/token-keeper.{out,err}.log"
echo "Health: ${LOG_DIR}/health.json"
