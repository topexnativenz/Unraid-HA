# Flux UI (MD3) — parallel dashboard

Material Design 3–styled dashboard inspired by [ElementZoom/Flux-UI-Home-Assistant-Dashboard](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard). Installed **alongside** Mobile Home; does not modify `mobile-home` or its default panel settings.

## Phase 4 tablet (16:9)

`/flux-ui-tablet` follows the [ElementZoom MD3 Dynamic Tablet Dashboard](https://github.com/ElementZoom/Material-Design-3-Dynamic-Tablet-Dashboard) author framework (`dashboard.yaml` Overview grid): greeting · Climate/Toggles/Scenes `simple-tabs` · weather forecast · calendar · room selector · room cards · cameras · bottom nav.

Build: `python3 scripts/build_flux_ui.py --tablet` → `generated/lovelace.flux_ui_tablet.json`.

**rk3576_u RGB LED:** `packages/flux_ui_tablet_led.yaml` pulses
`light.rk3576_u_rk3576_u_rgb` (MQTT AndroidTablet Controls → RGB) green while
Model S / Model X report charging. Override via `input_text.flux_ui_tablet_rgb_led`
if discovery used a different ID.

**Tablet cameras:** overview row is Reolink Back Courtyard → Eufy Driveway →
Front door Doorbell → Garage Door (`entities.yaml` → `tablet.overview_cameras`).
Unused Eufy cameras (Front Yard, Side of House, Clubrooms, Showroom) are disabled
via `scripts/fix_eufy_cameras.py` (runs on deploy).

## Phase 3 (mobile): Context-aware overview + ElementZoom tabs

Mobile overview follows [ElementZoom/Flux-UI-Home-Assistant-Dashboard](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard) (`dashboard/mobile/views/01-overview.yaml`):

| Area | Description |
|------|-------------|
| Hero | Greeting + `weather.forecast_home` |
| Home status | Live chips: lights on count, garage state |
| **Home / Events / Active tabs** | `custom:simple-tabs` filter (ElementZoom reference) |
| **Home tab** | Quick Actions, Climate, Favourite lights |
| **Events tab** | `calendar-card-pro` timeline (or mushroom fallback) |
| **Active tab** | Active now lights + doors open alert (shown when anything is on/open) |

Config: [`overview_tabs.yaml`](overview_tabs.yaml), [`context.yaml`](context.yaml), [`rooms.yaml`](rooms.yaml). See [`ROADMAP.md`](ROADMAP.md) for Phase 4.

Entity map: [`entities.yaml`](entities.yaml)

## Prerequisites

- Home Assistant with long-lived access token in `~/.cursor/mcp.json` (same as other deploy scripts)
- **HACS** with these frontend plugins (install before deploy):

| HACS repo | Purpose |
|-----------|---------|
| [piitaya/lovelace-mushroom](https://github.com/piitaya/lovelace-mushroom) | Overview cards |
| [thomasloven/lovelace-card-mod](https://github.com/thomasloven/lovelace-card-mod) | MD3 glass styling |
| [custom-cards/button-card](https://github.com/custom-cards/button-card) | Future Flux views |
| [thomasloven/lovelace-layout-card](https://github.com/thomasloven/lovelace-layout-card) | 16:9 tablet `grid-layout` overview |
| [custom-cards/stack-in-card](https://github.com/custom-cards/stack-in-card) | Card stacking |
| [thomasloven/lovelace-auto-entities](https://github.com/thomasloven/lovelace-auto-entities) | Active tab — lights currently on |
| [agoberg85/home-assistant-simple-tabs](https://github.com/agoberg85/home-assistant-simple-tabs) | **Home / Events / Active** overview tabs ([ElementZoom ref](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard)) |
| [alexpfau/calendar-card-pro](https://github.com/alexpfau/calendar-card-pro) | Events tab timeline ([ElementZoom ref](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard)) |
| [joseluis9595/lovelace-navbar-card](https://github.com/joseluis9595/lovelace-navbar-card) | Bottom nav |
| [maykar/kiosk-mode](https://github.com/maykar/kiosk-mode) | Hide HA header on mobile |
| [Nerwyn/material-you-theme](https://github.com/Nerwyn/material-you-theme) | Full MD3 theming (optional) |
| [Nerwyn/material-you-utilities](https://github.com/Nerwyn/material-you-utilities) | MD3 helpers (optional) |

Garage pulse buttons require [`garage_doors_pulse.yaml`](../garage-doors/packages/garage_doors_pulse.yaml) on HA. **Tapo sensor IDs** are configured in [`garage-doors/entities.yaml`](../garage-doors/entities.yaml) — icons show open/closed from contact sensors, not button toggles.

## Visual design (MD3 / Flux)

MD3 styling includes:

- **Dark MD3 theme** (`flux-ui-md3`) with Material You surface tokens
- **Wallpaper background** (`/local/flux-ui/wallpapers/dark-purple.webp`)
- **Glass cards** — blur, tinted surfaces, 28px corners
- **button-card templates** — hero, quick actions, light tiles
- **Bottom navbar** — Home / Rooms / Scenes / Camera / More (navbar-card HACS)
- **Kiosk mode** — hides HA header on mobile

After deploy: open Flux UI, hard-refresh browser (Cmd+Shift+R). On iOS Companion: **Reset Frontend Cache**.

Optional: install [Material You Theme](https://github.com/Nerwyn/material-you-theme) via HACS for dynamic accent colours per user.

## Deploy (E2E)

From your Mac on the same LAN as HA:

```bash
cd /Users/topexnative/Projects/unraid-array-design
bash home-assistant/flux-ui-dashboard/scripts/update_and_deploy.sh
```

Or pull + deploy manually (**do not** put a SHA after `git reset --hard` — that
means pathspec and fails with `Cannot do hard reset with paths`, leaving you on
an old commit so LED / layout changes never deploy):

```bash
cd /Users/topexnative/Projects/unraid-array-design
git fetch origin cursor/flux-ui-md3-dashboard-bf3a
git checkout cursor/flux-ui-md3-dashboard-bf3a
git reset --hard origin/cursor/flux-ui-md3-dashboard-bf3a
git rev-parse --short HEAD   # confirm SHA matches the PR tip before deploying
ls home-assistant/flux-ui-dashboard/packages/flux_ui_tablet_led.yaml
bash home-assistant/scripts/run_all_e2e.sh
```

Deploy log must show:
- `Deploy source: … @ <expected SHA>` (not an older tip)
- `copied packages/flux_ui_tablet_led.yaml`
- `loaded binary_sensor.flux_ui_ev_charging` / `script.flux_ui_tablet_led_charge_pulse`
- tablet music uses `mediocre-media-player-card` (compact), not the old multi/panel card

```bash
# Token: HA_TOKEN env, --token flag, or ~/.cursor/mcp.json (homeassistant MCP)
export HA_TOKEN="your-long-lived-token"   # optional if mcp.json exists
export HA_URL="http://192.168.1.239:8123" # optional
```

One-shot script: downloads Mushroom + card-mod JS → builds overview → verifies entities → mounts Samba → copies theme/www/packages/storage → registers dashboard via WebSocket → live verify.

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

## Verify Phase 3

```bash
python3 home-assistant/flux-ui-dashboard/scripts/verify_phase3.py
```

Expect `(23 views, 4 overview sections)` with tabs layout and deploy log `phase3=True`.

### Overview tabs setup

1. Install **simple-tabs** and **calendar-card-pro** via HACS (see table above).
2. Edit [`overview_tabs.yaml`](overview_tabs.yaml) — add your `calendar.*` entities.
3. Redeploy. The **Active** tab auto-hides when no lights/doors are open (ElementZoom pattern).

Reference: [ElementZoom/Flux-UI-Home-Assistant-Dashboard](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard) → `dashboard/mobile/views/01-overview.yaml`

## Roadmap

See [`ROADMAP.md`](ROADMAP.md) — Phase 4: camera overlay, media layout, tablet dashboard.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Still Mushroom cards / no MD3 | `git pull` failed — run `update_and_deploy.sh`. Deploy log must show `overview_sections=8`, `phase3=True`. |
| `git pull` blocked by local changes | `git stash` then pull, or use `update_and_deploy.sh` |
| Wrong dashboard open | URL must be `/flux-ui/overview`, not `/mobile-home/home` |
| `custom:mushroom-*` errors | Install Mushroom via HACS; hard-refresh browser |
| Climate shows fallback | Run deploy with SMB mount so Mobile Home storage is readable |
| Dashboard not in sidebar | Re-run deploy (creates `flux-ui` via API) |
| Garage buttons no-op | Deploy garage pulse package |
| Styling unchanged after deploy | Hard-refresh (Cmd+Shift+R); iOS Companion → Reset Frontend Cache |
