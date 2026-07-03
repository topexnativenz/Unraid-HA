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

Garage pulse buttons require [`garage_doors_pulse.yaml`](../garage-doors/packages/garage_doors_pulse.yaml) on HA.

## Deploy (E2E)

From your Mac on the same LAN as HA:

```bash
# Token: HA_TOKEN env, --token flag, or ~/.cursor/mcp.json (homeassistant MCP)
export HA_TOKEN="your-long-lived-token"   # optional if mcp.json exists
export HA_URL="http://192.168.1.239:8123" # optional

bash home-assistant/flux-ui-dashboard/scripts/setup_e2e.sh
```

One-shot script: downloads Mushroom + card-mod JS → builds overview → verifies entities → mounts Samba → copies theme/www/storage → registers dashboard via WebSocket → live verify.

Manual steps:

```bash
pip install -r home-assistant/flux-ui-dashboard/requirements.txt
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

## Roadmap

- [ ] Tablet dashboard + shared YAML partials (Flux architecture)
- [ ] Rooms, cameras, Tesla tabs
- [ ] Material You dynamic colours per user
- [ ] Kiosk mode for wall tablet

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `custom:mushroom-*` errors | Install Mushroom via HACS; hard-refresh browser |
| Climate shows fallback | Run deploy with SMB mount so Mobile Home storage is readable |
| Dashboard not in sidebar | Re-run deploy (creates `flux-ui` via API) |
| Garage buttons no-op | Deploy garage pulse package |
