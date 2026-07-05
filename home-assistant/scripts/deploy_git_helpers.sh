#!/usr/bin/env bash
# Shared git helpers for Mac/cloud deploy — avoid autostash conflicts on generated files.

# Files rewritten by discover_* / build during every E2E deploy.
# Local edits block git pull and cause autostash merge conflicts on Mac.
flux_deploy_generated_paths() {
  local ha_dir="$1"
  cat <<EOF
${ha_dir}/flux-ui-dashboard/media_players.yaml
${ha_dir}/flux-ui-dashboard/packages/flux_ui_media.yaml
${ha_dir}/flux-ui-dashboard/www/flux-ui/carousel-sync.js
${ha_dir}/flux-ui-dashboard/room_sensors.yaml
EOF
}

reset_flux_deploy_generated_files() {
  local git_root="$1"
  local ha_dir="$2"
  local path
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    if [[ ! -e "$git_root/$path" ]]; then
      continue
    fi
    if grep -q '^<<<<<<< ' "$git_root/$path" 2>/dev/null; then
      echo "    Conflict markers in $path — restoring from git"
      git -C "$git_root" checkout -- "$path" 2>/dev/null || rm -f "$git_root/$path"
      continue
    fi
    if ! git -C "$git_root" diff --quiet HEAD -- "$path" 2>/dev/null; then
      echo "    Resetting local $path (regenerated on deploy)"
      git -C "$git_root" checkout -- "$path" 2>/dev/null || true
    fi
  done < <(flux_deploy_generated_paths "$ha_dir")
}
