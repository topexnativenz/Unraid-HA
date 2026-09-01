#!/bin/bash
# Deploy garage packages + automations to Home Assistant (preferred entry point).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${SCRIPT_DIR}/deploy_garage_doors.py" "$@"
