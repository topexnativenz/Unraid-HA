#!/bin/bash
# Docker container update check + apply during 00:00-07:00 Pacific/Auckland.
# Check uses Unraid dynamix update-status; apply uses official update_container script.
set -euo pipefail

TZ=Pacific/Auckland
export TZ

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_PHP="${SCRIPT_DIR}/docker-update-check.php"
UPDATE_BIN=/usr/local/emhttp/plugins/dynamix.docker.manager/scripts/update_container
QUEUE_SH=/boot/config/scripts/maintenance-queue.sh

PENDING=/boot/config/docker-update-pending.txt
EXCLUDE=/boot/config/docker-update-exclude.txt
STOP_FLAG=/boot/config/docker-update-apply.stop
LOG=/var/log/docker-update-maintenance.log
TASK_ID=T-docker-updates

# Max containers per maintenance window (light; stack with parity if non-media only).
MAX_PER_RUN="${DOCKER_UPDATE_MAX_PER_RUN:-4}"

# Skip media stack updates while correcting parity runs (array-heavy).
MEDIA_PATTERN='plex|sonarr|radarr|prowlarr|sabnzbd|overseerr|tautulli|lidarr|readarr'

log() { echo "$(date -Iseconds) $*" | tee -a "$LOG"; }

is_in_window() {
  local h
  h=$(date +%H)
  [[ "$h" -lt 7 ]]
}

parity_busy() {
  local busy action
  busy=$(grep -Pom1 '^mdResync=\K.*' /proc/mdstat 2>/dev/null || echo 0)
  action=$(grep -Pom1 '^mdResyncAction=\K.*' /proc/mdstat 2>/dev/null || echo '')
  [[ "${busy:-0}" -gt 0 && "$action" == check\ P* ]]
}

is_excluded() {
  local name="$1"
  local line
  [[ -f "$EXCLUDE" ]] || return 1
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"
    line="$(echo "$line" | xargs)"
    [[ -z "$line" ]] && continue
    if [[ "${name,,}" == *"${line,,}"* ]]; then
      return 0
    fi
  done <"$EXCLUDE"
  return 1
}

is_media() {
  local name="$1"
  [[ "${name,,}" =~ $MEDIA_PATTERN ]]
}

should_skip_for_parity() {
  local name="$1"
  parity_busy && is_media "$name"
}

queue_helper() {
  [[ -x "$QUEUE_SH" ]] && bash "$QUEUE_SH" "$@"
}

run_check() {
  if [[ ! -x "$CHECK_PHP" ]]; then
    log "ERROR: missing $CHECK_PHP"
    exit 1
  fi

  log "check: scanning for container image updates"
  local tmp pending_count=0
  tmp="$(mktemp)"
  : >"$tmp"

  while IFS='|' read -r cname template repo; do
    [[ -z "$cname" ]] && continue
    if is_excluded "$cname"; then
      log "check: skip excluded $cname"
      continue
    fi
    echo "${cname}|${template}|${repo}|$(date -Iseconds)" >>"$tmp"
    pending_count=$((pending_count + 1))
  done < <("$CHECK_PHP" 2>>"$LOG")

  mv "$tmp" "$PENDING"
  log "check: $pending_count container(s) pending → $PENDING"

  if [[ "$pending_count" -gt 0 ]] && [[ -x "$QUEUE_SH" ]]; then
    local apply_date desc
    if is_in_window; then
      apply_date="$(date +%Y-%m-%d)"
    else
      apply_date="$(date +%Y-%m-%d)"
      if [[ "$(date +%H)" -ge 7 ]]; then
        apply_date="$(date -d 'tomorrow' +%Y-%m-%d 2>/dev/null || date -v+1d +%Y-%m-%d)"
      fi
    fi
    desc="Docker updates: ${pending_count} container(s) pending"
    if ! grep -v '^#' /boot/config/maintenance-queue.txt 2>/dev/null \
      | grep -qF "${apply_date}|${TASK_ID}|"; then
      queue_helper queue "$apply_date" "$TASK_ID" light "$desc" 2>/dev/null || true
      log "check: queued $TASK_ID on $apply_date ($desc)"
    fi
  fi
}

run_apply() {
  if [[ -f "$STOP_FLAG" ]]; then
    log "apply: stopped by flag $STOP_FLAG"
    exit 0
  fi

  if ! is_in_window; then
    log "apply: outside 00:00-07:00 window — deferring"
    exit 0
  fi

  if [[ ! -f "$PENDING" ]] || [[ ! -s "$PENDING" ]]; then
    log "apply: nothing pending"
    exit 0
  fi

  if [[ -x "$QUEUE_SH" ]]; then
    if ! queue_helper can-run light >/dev/null 2>&1; then
      log "apply: maintenance-queue declined light work: $(queue_helper can-run light 2>&1 || true)"
      exit 0
    fi
  fi

  log "apply: starting (max $MAX_PER_RUN per run, parity_busy=$(parity_busy && echo yes || echo no))"
  local applied=0
  local remaining=()
  local line cname template repo checked

  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    IFS='|' read -r cname template repo checked <<<"$line"

    if is_excluded "$cname"; then
      log "apply: skip excluded $cname"
      continue
    fi

    if should_skip_for_parity "$cname"; then
      log "apply: defer $cname (media + parity busy)"
      remaining+=("$line")
      continue
    fi

    if [[ "$applied" -ge "$MAX_PER_RUN" ]]; then
      remaining+=("$line")
      continue
    fi

    if [[ ! -x "$UPDATE_BIN" ]]; then
      log "apply: ERROR missing $UPDATE_BIN"
      exit 1
    fi

    log "apply: updating $cname (template=$template, image=$repo)"
    encoded="$(php -r 'echo rawurlencode($argv[1]);' "$template")"
    if "$UPDATE_BIN" "$encoded" >>"$LOG" 2>&1; then
      applied=$((applied + 1))
      log "apply: OK $cname"
    else
      log "apply: FAILED $cname — will retry next window"
      remaining+=("$line")
    fi
  done <"$PENDING"

  if [[ ${#remaining[@]} -gt 0 ]]; then
    printf '%s\n' "${remaining[@]}" >"$PENDING"
    log "apply: $applied updated, ${#remaining[@]} still pending"
  else
    : >"$PENDING"
    log "apply: $applied updated, queue empty"
  fi
}

run_stop() {
  touch "$STOP_FLAG"
  log "stop: set $STOP_FLAG — in-flight update may finish; no new starts until resume"
}

run_resume() {
  rm -f "$STOP_FLAG"
  log "resume: cleared $STOP_FLAG"
}

run_status() {
  echo "timezone=Pacific/Auckland"
  echo "now=$(date -Iseconds)"
  echo "in_window=$(is_in_window && echo yes || echo no)"
  echo "parity_busy=$(parity_busy && echo yes || echo no)"
  echo "stop_flag=$([[ -f $STOP_FLAG ]] && echo yes || echo no)"
  echo "pending_file=$PENDING"
  if [[ -f "$PENDING" ]]; then
    echo "---pending---"
    cat "$PENDING" 2>/dev/null || true
  else
    echo "---pending--- (none)"
  fi
  if [[ -x "$QUEUE_SH" ]]; then
    echo "---maintenance-queue---"
    queue_helper status 2>/dev/null || true
  fi
  echo "---log tail---"
  tail -n 15 "$LOG" 2>/dev/null || echo "(no log yet)"
}

case "${1:-}" in
  check)  run_check ;;
  apply)  run_apply ;;
  stop)   run_stop ;;
  resume) run_resume ;;
  status) run_status ;;
  *)
    echo "usage: $0 {check|apply|stop|resume|status}" >&2
    echo "  check  — daytime OK; refresh pending list + queue light task" >&2
    echo "  apply  — 00:00-07:00 only; run up to $MAX_PER_RUN updates" >&2
    exit 1
    ;;
esac
