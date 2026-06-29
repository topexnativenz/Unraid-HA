#!/bin/bash
# Deploy docker-update maintenance scripts to tower and install cron in crontab via /boot/config/go
set -euo pipefail

REPO_ROOT="/Users/topexnative/Projects/unraid-array-design"
SRC="${REPO_ROOT}/tower/boot/config"
DEST_SCRIPTS="/boot/config/scripts"
DEST_CONFIG="/boot/config"
MARKER="docker-update-maintenance"

TOWER_HOST="$("${REPO_ROOT}/tower/scripts/tower-resolve-host.sh")"
TOWER_VIA="$("${REPO_ROOT}/tower/scripts/tower-resolve-host.sh" --via)"
SSH=(ssh -o ConnectTimeout=15 -o IdentitiesOnly=yes tower)
SCP=(scp -o ConnectTimeout=15 -o IdentitiesOnly=yes)

echo "Deploying via ${TOWER_VIA} (${TOWER_HOST})..."

"${SSH[@]}" "mkdir -p ${DEST_SCRIPTS} /boot/config/snippets"

"${SCP[@]}" "${SRC}/scripts/docker-update-maintenance.sh" \
    "${SRC}/scripts/docker-update-check.php" \
    "tower:${DEST_SCRIPTS}/"

"${SCP[@]}" "${SRC}/docker-update-exclude.txt" "tower:${DEST_CONFIG}/docker-update-exclude.txt"

"${SSH[@]}" "chmod 755 ${DEST_SCRIPTS}/docker-update-maintenance.sh ${DEST_SCRIPTS}/docker-update-check.php"
"${SSH[@]}" "chmod 644 ${DEST_CONFIG}/docker-update-exclude.txt"

# Ensure /boot/config/go merges docker-update lines into crontab (never as bare shell commands).
"${SSH[@]}" bash <<'REMOTE'
set -euo pipefail
GO=/boot/config/go
if grep -q 'docker-update-maintenance.sh check' "$GO" 2>/dev/null && \
   grep -q 'grep -vE.*docker-update-maintenance' "$GO" 2>/dev/null; then
  echo "go crontab block already includes docker-update-maintenance"
  exit 0
fi

# Remove legacy broken append (raw cron lines outside crontab block)
sed -i '/# docker-update-maintenance (unraid-array-design)/,/^5 0 \* \* \*.*docker-update-maintenance.sh resume/d' "$GO" 2>/dev/null || true

python3 <<'PY'
from pathlib import Path
go = Path("/boot/config/go")
text = go.read_text()
docker_lines = [
    ' echo "45 17 * * * /usr/bin/bash /boot/config/scripts/docker-update-maintenance.sh check >>/var/log/docker-update-maintenance.log 2>&1"; \\',
    ' echo "15 1 * * * /usr/bin/bash /boot/config/scripts/docker-update-maintenance.sh apply >>/var/log/docker-update-maintenance.log 2>&1"; \\',
    ' echo "0 7 * * * /usr/bin/bash /boot/config/scripts/docker-update-maintenance.sh stop >>/var/log/docker-update-maintenance.log 2>&1"; \\',
    ' echo "5 0 * * * /usr/bin/bash /boot/config/scripts/docker-update-maintenance.sh resume >>/var/log/docker-update-maintenance.log 2>&1") | crontab -',
]
if "docker-update-maintenance" in text and "grep -vE" in text:
    print("already patched")
    raise SystemExit(0)
if "grep -vE" in text:
    old = ' echo "0 7 * * * bash /boot/config/scripts/parity-correcting-maintenance.sh pause >> /var/log/parity-correcting-maintenance.log 2>&1") | crontab -'
    new = ' echo "0 7 * * * bash /boot/config/scripts/parity-correcting-maintenance.sh pause >> /var/log/parity-correcting-maintenance.log 2>&1"; \\\n' + "\n".join(docker_lines)
    if old not in text:
        raise SystemExit("go file format unexpected — patch manually")
    text = text.replace(old, new)
    text = text.replace(
        "grep -v 'plex-db-maintenance\\|plex-arr-cleanup\\|parity-correcting-maintenance'",
        "grep -vE 'plex-db-maintenance|plex-arr-cleanup|parity-correcting-maintenance|docker-update-maintenance'",
    )
else:
    raise SystemExit("go file missing crontab block — patch manually")
go.write_text(text)
print("patched go crontab block")
PY
REMOTE

echo "Verify:"
"${SSH[@]}" "bash ${DEST_SCRIPTS}/docker-update-maintenance.sh status"
