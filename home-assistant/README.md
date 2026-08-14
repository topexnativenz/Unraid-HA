# Home Assistant (Three Mile Bush)

LAN instance: **http://192.168.1.239:8123**

Companion apps and Lovelace admin from anywhere use **Nabu Casa Remote UI** (already connected). The Mac does not need to stay on the LAN, and nothing needs to be left running at home.

| Area | Doc |
|------|-----|
| Remote admin / phone ship | this file |
| Flux UI (phone + 16:9 tablet) | [flux-ui-dashboard/README.md](flux-ui-dashboard/README.md) |
| Mobile Home | [mobile-dashboard/README.md](mobile-dashboard/README.md) |
| Solar | [solar-dashboard/README.md](solar-dashboard/README.md) |
| Gate | [gate/README.md](gate/README.md) |
| Garage doors | [garage-doors/README.md](garage-doors/README.md) |

## How dashboards get to HA

| Path | What it does | Works off-LAN? |
|------|----------------|----------------|
| `lovelace/config/save` (API) | Live Lovelace (Flux UI, tablet) | **Yes** — LAN or Nabu Casa |
| Samba `config` share | Packages, themes, `/config/www` assets | **No** — LAN or VPN only |
| GitHub Action **Deploy Lovelace** | API-only Flux UI / tablet push | **Yes** — uses Nabu Casa |

## Resolve HA (LAN first)

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/scripts/ha_resolve.py --json
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/scripts/ha_resolve.py --cache
bash /Users/topexnative/Projects/unraid-array-design/home-assistant/scripts/sync-cursor-ha-mcp.sh
```

`--cache` (on LAN once) writes `/Users/topexnative/.cursor/ha-remote.json` so travel falls back to Nabu Casa. Do not commit that file.

Deploy scripts call the same resolver. Off-LAN they skip Samba and push Lovelace over the API (`--api-only`).

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/flux-ui-dashboard/scripts/deploy_flux_ui.py --api-only
```

## Phone: commit and ship without the Mac

1. Edit Lovelace YAML on GitHub (app, [github.dev](https://github.dev/topexnativenz/Unraid-HA), or Working Copy).
2. Commit to `cursor/flux-ui-md3-dashboard-bf3a` (auto-deploys when Flux YAML changes) **or** run **Actions → Deploy Lovelace → Run workflow**.
3. GitHub secrets (repo **Settings → Secrets**):
   - `HA_URL` — Nabu Casa origin (`https://….ui.nabu.casa`, no path)
   - `HA_TOKEN` — long-lived HA token (same kind as Cursor MCP)

Packages, camera WebPs, and Casa Luna JS still need a LAN/VPN Samba deploy.

## Companion (phones)

Nabu Casa Remote UI is the remote path. Do not put a Tailscale URL in Companion. On Wi‑Fi at home the app uses the LAN address by itself.
