#!/bin/bash
# ssh to tower with LAN-first host resolution.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="$("${REPO_ROOT}/scripts/tower-resolve-host.sh")"
VIA="$("${REPO_ROOT}/scripts/tower-resolve-host.sh" --via)"

echo "tower-ssh: via=${VIA} host=${HOST}" >&2
exec ssh -o ConnectTimeout=15 -o IdentitiesOnly=yes tower "$@"
