#!/bin/bash
# Copy garage_doors_pulse.yaml to HA and sync tracked open state from Tapo sensors.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/deploy_garage_doors_pulse.py" "$@"
