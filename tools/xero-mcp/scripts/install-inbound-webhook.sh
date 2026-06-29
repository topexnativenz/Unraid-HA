#!/bin/bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="${REPO_ROOT}/.venv/bin/python"
LABEL="com.unraid-array-design.xero-inbound-webhook"
PLIST_DEST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="${HOME}/.config/xero-mcp/inbound"
TEMPLATE="${REPO_ROOT}/scripts/com.unraid-array-design.xero-inbound-webhook.plist.template"

mkdir -p "${LOG_DIR}" "${HOME}/Library/LaunchAgents"
sed \
  -e "s|__VENV_PY__|${VENV_PY}|g" \
  -e "s|__LOG_DIR__|${LOG_DIR}|g" \
  "${TEMPLATE}" > "${PLIST_DEST}"

launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${PLIST_DEST}"
launchctl enable "gui/$(id -u)/${LABEL}" 2>/dev/null || true
echo "Inbound webhook launchd: ${PLIST_DEST}"
