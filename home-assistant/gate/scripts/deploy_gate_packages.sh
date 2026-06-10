#!/usr/bin/env bash
# Deploy gate packages + automations block to Home Assistant via SMB.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=""

# Prefer a Python outside the active .venv (system Python usually has websockets).
for candidate in /opt/homebrew/bin/python3 /usr/bin/python3 /usr/local/bin/python3 python3; do
  if [ -x "${candidate}" ] && "${candidate}" -c "import websockets" 2>/dev/null; then
    PYTHON="${candidate}"
    break
  fi
done

if [ -z "${PYTHON}" ]; then
  if [ -n "${VIRTUAL_ENV:-}" ]; then
    echo "Active .venv does not include websockets; trying system Python without VIRTUAL_ENV." >&2
    for candidate in /opt/homebrew/bin/python3 /usr/bin/python3 /usr/local/bin/python3; do
      if [ -x "${candidate}" ]; then
        if env -u VIRTUAL_ENV "${candidate}" -c "import websockets" 2>/dev/null; then
          PYTHON="${candidate}"
          break
        fi
      fi
    done
  fi
fi

if [ -z "${PYTHON}" ]; then
  if [ -n "${HA_SAMBA_PASSWORD:-}" ]; then
    PYTHON="$(command -v python3)"
    echo "Using HA_SAMBA_PASSWORD (no websockets needed)." >&2
  else
    cat >&2 <<'EOF'
Could not find a Python with the 'websockets' package.

Fix one of:
  python3 -m pip install --user websockets
  deactivate   # leave .venv, then re-run this script
  export HA_SAMBA_PASSWORD='…'   # HA → Settings → Add-ons → Samba share → Options

Then run:
  /Users/topexnative/Projects/unraid-array-design/home-assistant/gate/scripts/deploy_gate_packages.sh
EOF
    exit 1
  fi
fi

if [ -n "${VIRTUAL_ENV:-}" ] && [ "${PYTHON}" != "$(command -v python3)" ]; then
  exec env -u VIRTUAL_ENV "${PYTHON}" "${SCRIPT_DIR}/deploy_gate_packages.py" "$@"
else
  exec "${PYTHON}" "${SCRIPT_DIR}/deploy_gate_packages.py" "$@"
fi
