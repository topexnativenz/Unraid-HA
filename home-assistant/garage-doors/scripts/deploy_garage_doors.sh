#!/bin/bash
# Deploy garage packages + automations to Home Assistant (preferred entry point).
set -euo pipefail
exec python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/garage-doors/scripts/deploy_garage_doors.py "$@"
