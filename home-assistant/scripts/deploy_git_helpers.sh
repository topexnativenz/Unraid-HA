#!/usr/bin/env bash
# Shared git helpers for Mac/cloud deploy — avoid autostash conflicts on generated files.

# Files rewritten by discover_* / build during every E2E deploy.
flux_deploy_generated_paths() {
  local ha_dir="$1"
  cat <<EOF
${ha_dir}/flux-ui-dashboard/media_players.yaml
${ha_dir}/flux-ui-dashboard/packages/flux_ui_media.yaml
${ha_dir}/flux-ui-dashboard/www/flux-ui/carousel-sync.js
${ha_dir}/flux-ui-dashboard/room_sensors.yaml
EOF
}

# True when git index has unmerged entries (autostash / pull conflict).
git_has_unmerged_files() {
  local git_root="$1"
  git -C "$git_root" ls-files -u | grep -q .
}

restore_one_generated_file() {
  local git_root="$1"
  local path="$2"
  local full="$git_root/$path"

  if [[ ! -e "$full" ]] && ! git -C "$git_root" ls-files --error-unmatch "$path" >/dev/null 2>&1; then
    return 0
  fi

  # Unmerged or conflict markers — force restore from HEAD.
  if git -C "$git_root" ls-files -u -- "$path" | grep -q . || grep -q '^<<<<<<< ' "$full" 2>/dev/null; then
    echo "    Unmerged $path — restoring from HEAD"
    git -C "$git_root" rm -f --cached "$path" 2>/dev/null || true
    git -C "$git_root" checkout HEAD -- "$path" 2>/dev/null \
      || git -C "$git_root" show "HEAD:$path" >"$full" 2>/dev/null \
      || rm -f "$full"
    git -C "$git_root" add "$path" 2>/dev/null || true
    return 0
  fi

  if ! git -C "$git_root" diff --quiet HEAD -- "$path" 2>/dev/null; then
    echo "    Resetting local $path (regenerated on deploy)"
    git -C "$git_root" checkout -- "$path" 2>/dev/null || true
  fi
}

reset_flux_deploy_generated_files() {
  local git_root="$1"
  local ha_dir="$2"
  local path
  while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    restore_one_generated_file "$git_root" "$path"
  done < <(flux_deploy_generated_paths "$ha_dir")
}

# Abort in-progress merge/rebase and hard-sync branch to origin when still broken.
repair_deploy_git_state() {
  local git_root="$1"
  local branch="$2"
  local ha_dir="$3"

  if git -C "$git_root" rev-parse --git-dir >/dev/null 2>&1; then
    if [[ -d "$git_root/.git/rebase-merge" ]] || [[ -d "$git_root/.git/rebase-apply" ]]; then
      echo "    Aborting in-progress git rebase"
      git -C "$git_root" rebase --abort 2>/dev/null || true
    fi
    if [[ -f "$git_root/.git/MERGE_HEAD" ]]; then
      echo "    Aborting in-progress git merge"
      git -C "$git_root" merge --abort 2>/dev/null || true
    fi
  fi

  reset_flux_deploy_generated_files "$git_root" "$ha_dir"

  if git_has_unmerged_files "$git_root"; then
    echo "    Unmerged files remain — hard reset to origin/${branch}"
    git -C "$git_root" fetch origin "$branch" 2>/dev/null || git -C "$git_root" fetch origin
    git -C "$git_root" reset --hard "origin/${branch}"
  fi
}
