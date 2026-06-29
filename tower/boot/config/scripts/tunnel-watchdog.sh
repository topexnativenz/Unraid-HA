#!/bin/bash
# Restart cloudflared/swag if Docker shows them stopped (lightweight; safe anytime)
set -euo pipefail
LOG=/var/log/tunnel-watchdog.log
for c in cloudflared swag; do
  running=$(docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null || echo false)
  if [ "$running" != "true" ]; then
    echo "$(date -Iseconds) starting $c" >>"$LOG"
    docker start "$c" >>"$LOG" 2>&1 || true
  fi
done
