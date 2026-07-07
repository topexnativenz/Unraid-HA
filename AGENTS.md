# Agent instructions — Home Assistant / Flux UI tasks

When working on **Flux UI**, **Mobile Home**, **garage doors**, or any `home-assistant/` dashboard task, every session must finish with a **full live E2E deploy**. Do not ask the user to run scripts on their Mac.

## Required workflow (every task)

1. Implement and verify changes locally (build scripts, linters as applicable).
2. **Commit and push** to the feature branch.
3. **Run cloud E2E deploy** (mandatory before marking the task complete):

```bash
bash home-assistant/scripts/deploy_cloud.sh
```

4. If package helpers (`input_select.flux_ui_rooms_tab`, `input_select.flux_ui_media_player`) fail to load:

```bash
bash home-assistant/scripts/deploy_cloud.sh --restart-ha
```

5. Create or update the PR.

## Credentials (one-time setup)

Cloud agents need live Home Assistant access. Configure **Cursor Cloud Agent secrets** (or copy `.secrets/ha.env.example` → `.secrets/ha.env`):

| Variable | Required | Purpose |
|----------|----------|---------|
| `HA_URL` | Yes | Nabu Casa URL (`https://….ui.nabu.casa`) or LAN URL |
| `HA_TOKEN` | Yes | Long-lived access token |
| `HA_HOST` | Optional | LAN/Tailscale IP for Samba package push |
| `HA_SSH_HOST` | Optional | Tailscale SSH host when SMB unreachable from cloud |
| `HA_SSH_USER` | Optional | SSH user for package sync |
| `HA_SSH_KEY_PATH` | Optional | Private key for SSH |

Without `HA_TOKEN` / `HA_URL`, deploy falls back to **build-only** (no live push).

## Mac vs cloud

| Script | When |
|--------|------|
| `home-assistant/scripts/deploy_cloud.sh` | **Cloud agents, iOS Cursor, remote tasks** |
| `home-assistant/scripts/deploy_mac.sh` | Optional local Mac convenience (git pull + same E2E) |

## What deploy_cloud.sh does

1. Validates HA credentials and reachability
2. Builds Flux UI (assets → build → verify)
3. Deploys Lovelace via HA WebSocket API
4. Runs Sonos/garage/room discovery against live HA
5. Pushes packages/www/themes via SMB or SSH when reachable
6. Reloads package helpers and runs live verification

## Do not

- Ask the user to `git pull && bash deploy_mac.sh` after agent work
- Skip deploy for dashboard/UI changes
- Commit secrets (`.secrets/ha.env` is gitignored)
