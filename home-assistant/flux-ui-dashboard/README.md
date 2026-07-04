# Flux UI (MD3) — parallel dashboard

Material Design 3–styled dashboard inspired by [ElementZoom/Flux-UI-Home-Assistant-Dashboard](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard). Installed **alongside** Mobile Home; does not modify `mobile-home` or its default panel settings.

## Phase 1 (current): Overview

Overview mirrors the **Mobile Home → Home** tab:

| Section | Mobile Home entities |
|---------|---------------------|
| Header | Date/time + `weather.forecast_home` |
| Climate | Copied from live Mobile Home storage on deploy |
| Quick Actions | Gate locks, 3× garage pulse, All Off, Goodnight |
| Favourite lights | Same 8 lights as `TOP_FIVE` in `build_mobile_home.py` |

Entity map: [`entities.yaml`](entities.yaml)

## Prerequisites

- Home Assistant with long-lived access token in `~/.cursor/mcp.json` (same as other deploy scripts)
- **HACS** with these frontend plugins (install before deploy):

| HACS repo | Purpose |
|-----------|---------|
| [piitaya/lovelace-mushroom](https://github.com/piitaya/lovelace-mushroom) | Overview cards |
| [thomasloven/lovelace-card-mod](https://github.com/thomasloven/lovelace-card-mod) | MD3 glass styling |
| [custom-cards/button-card](https://github.com/custom-cards/button-card) | Future Flux views |
| [thomasloven/lovelace-layout-card](https://github.com/thomasloven/lovelace-layout-card) | Future tablet layout |
| [custom-cards/stack-in-card](https://github.com/custom-cards/stack-in-card) | Card stacking |
| [Clooos/bubble-card](https://github.com/Clooos/bubble-card) | Popups (phase 2) |
| [joseluis9595/lovelace-navbar-card](https://github.com/joseluis9595/lovelace-navbar-card) | Bottom nav (phase 2) |
| [Nerwyn/material-you-theme](https://github.com/Nerwyn/material-you-theme) | Full MD3 theming (optional) |
| [Nerwyn/material-you-utilities](https://github.com/Nerwyn/material-you-utilities) | MD3 helpers (optional) |

Garage pulse buttons require [`garage_doors_pulse.yaml`](../garage-doors/packages/garage_doors_pulse.yaml) on HA. **Tapo sensor IDs** are configured in [`garage-doors/entities.yaml`](../garage-doors/entities.yaml) — icons show open/closed from contact sensors, not button toggles.

## Visual design (MD3 / Flux)

Phase 2 styling includes:

- **Dark MD3 theme** (`flux-ui-md3`) with Material You surface tokens
- **Wallpaper background** (`/local/flux-ui/wallpapers/dark-purple.webp`)
- **Glass cards** — blur, tinted surfaces, 28px corners
- **button-card templates** — greeting header, quick actions, light tiles
- **Bottom navbar** — Flux / Mobile / Solar shortcuts (requires navbar-card HACS)
- **Climate section** — imported from Mobile Home, glass-wrapped

After deploy: open Flux UI, hard-refresh browser (Cmd+Shift+R). On iOS Companion: **Reset Frontend Cache**.

Optional: install [Material You Theme](https://github.com/Nerwyn/material-you-theme) via HACS for dynamic accent colours per user.

## Deploy (E2E)

From your Mac on the same LAN as HA:

```bash
cd /Users/topexnative/Projects/unraid-array-design

# Full pipeline: garage → Flux UI MD3 → Mobile Home
bash home-assistant/scripts/run_all_e2e.sh
```

Or pull latest MD3 branch first:

```bash
bash home-assistant/flux-ui-dashboard/scripts/update_and_deploy.sh
```

```bash
# Token: HA_TOKEN env, --token flag, or ~/.cursor/mcp.json (homeassistant MCP)
export HA_TOKEN="your-long-lived-token"   # optional if mcp.json exists
export HA_URL="http://192.168.1.239:8123" # optional

git stash
git pull origin cursor/flux-ui-md3-dashboard-bf3a
bash home-assistant/flux-ui-dashboard/scripts/setup_e2e.sh
```

One-shot script: downloads Mushroom + card-mod JS → builds overview → verifies entities → mounts Samba → copies theme/www/storage → registers dashboard via WebSocket → live verify.

Manual steps:

```bash
python3 -m pip install -r home-assistant/flux-ui-dashboard/requirements.txt
python3 home-assistant/flux-ui-dashboard/scripts/deploy_flux_ui.py
```

Open: **http://192.168.1.239:8123/flux-ui/overview**

### Offline / build only

```bash
python3 home-assistant/flux-ui-dashboard/scripts/deploy_flux_ui.py --offline-ok
python3 home-assistant/flux-ui-dashboard/scripts/verify_flux_ui.py
```

## iOS / default dashboard

Flux UI is **not** set as default. Mobile Home remains the primary phone dashboard. To try Flux UI on iPhone: **Profile → Dashboard → Flux UI**.

## Kiosk mode (hide HA header)

The Flux FB post hides the top **Overview** bar on phone. That requires **kiosk-mode** (HACS: [maykar/kiosk-mode](https://github.com/maykar/kiosk-mode)), not card-mod alone. Deploy adds:

```yaml
kiosk_mode:
  mobile_settings:
    hide_header: true
```

If you still see the header, install kiosk-mode in HACS → Frontend, then redeploy.

### How to reach settings when the header is hidden

| What you need | How |
|---------------|-----|
| **Theme, account, default dashboard** | **More → Profile** in the bottom nav, or **swipe from the left edge** to open the HA sidebar → Profile |
| **HA admin / integrations** | **More → HA Settings** |
| **Other dashboards** (Mobile Home, Solar) | **More** menu, or sidebar |
| **Companion app settings** (sensors, location, notifications) | Leave the dashboard: iOS **Settings → Home Assistant**, or open sidebar → Companion app settings link at bottom of Profile |
| **Emergency exit** | More → Mobile Home (full HA chrome returns on that dashboard) |

We **only hide the header**, not the sidebar — same as ElementZoom Flux. Swipe from the left edge still opens the drawer.

Temporary debug (show header): `python3 .../build_flux_ui.py --no-kiosk`

## Roadmap

- [ ] Tablet dashboard + shared YAML partials (Flux architecture)
- [ ] Rooms, cameras, Tesla tabs
- [ ] Material You dynamic colours per user
- [ ] Kiosk mode for wall tablet

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Still Mushroom cards / no MD3 | `git pull` failed — run `update_and_deploy.sh` (see above). Deploy log must show `sections=5`, not `4`. |
| `git pull` blocked by local changes | `git stash` then pull, or use `update_and_deploy.sh` |
| Wrong dashboard open | URL must be `/flux-ui/overview`, not `/mobile-home/home` |
| `custom:mushroom-*` errors | Install Mushroom via HACS; hard-refresh browser |
| Climate shows fallback | Run deploy with SMB mount so Mobile Home storage is readable |
| Dashboard not in sidebar | Re-run deploy (creates `flux-ui` via API) |
| Garage buttons no-op | Deploy garage pulse package |
| Styling unchanged after deploy | Hard-refresh (Cmd+Shift+R); iOS Companion → Reset Frontend Cache |
