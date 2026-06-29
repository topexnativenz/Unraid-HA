# Tower automation (Unraid flash scripts)

## SSH / MCP access from Mac (LAN first)

| Priority | Host | When |
|----------|------|------|
| 1 | `192.168.1.7` | On home LAN (`tower-on-lan` probe succeeds) |
| 2 | `100.79.125.103` | Tailscale connected (away from home) |

```bash
# Which path is active?
/Users/topexnative/Projects/unraid-array-design/tower/scripts/tower-resolve-host.sh --json

# ssh / deploy (auto-resolve)
ssh tower
bash /Users/topexnative/Projects/unraid-array-design/tower/scripts/deploy-docker-update-maintenance.sh

# Refresh Cursor MCP URLs after network change (LAN ↔ Tailscale)
/Users/topexnative/Projects/unraid-array-design/tower/scripts/sync-cursor-tower-mcp.sh
```

`ssh tower` uses OpenSSH **Match exec** in `~/.ssh/config`. Cursor **tower-ssh** MCP uses `tower/scripts/tower-ssh-mcp.sh` (same resolver). If tower is unreachable, start **Tailscale** when away or check LAN power.

Scripts here are **canonical copies** for `/boot/config` on tower:

```bash
bash /Users/topexnative/Projects/unraid-array-design/tower/scripts/deploy-docker-update-maintenance.sh
```

## Docker container updates

| File | On tower |
|------|----------|
| `boot/config/scripts/docker-update-maintenance.sh` | Orchestrator (`check`, `apply`, `status`) |
| `boot/config/scripts/docker-update-check.php` | Uses Unraid `DockerUpdate::reloadUpdateStatus()` |
| `boot/config/docker-update-exclude.txt` | Never auto-update (substring match on container name) |

**Policy:** Check **17:45** daily (network/registry only). Apply **01:15** only inside **00:00–07:00** NZ, up to **4** containers per night, **light** in `maintenance-queue.sh`. Media stack (`plex`, `*arr`, etc.) is **skipped while correcting parity** is running.

**Log:** `/var/log/docker-update-maintenance.log`

**Manual:**

```bash
ssh tower 'bash /boot/config/scripts/docker-update-maintenance.sh status'
ssh tower 'bash /boot/config/scripts/docker-update-maintenance.sh check'
# apply only inside window:
ssh tower 'bash /boot/config/scripts/docker-update-maintenance.sh apply'
```

Pin a container: add its name to `/boot/config/docker-update-exclude.txt` on tower.
