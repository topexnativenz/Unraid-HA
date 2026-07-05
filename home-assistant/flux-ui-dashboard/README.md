# Flux UI (MD3) — parallel dashboard

Material Design 3–styled dashboard inspired by [ElementZoom/Flux-UI-Home-Assistant-Dashboard](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard). Installed **alongside** Mobile Home; does not modify `mobile-home` or its default panel settings.

## Phase 3 (current): Context-aware overview + ElementZoom tabs

Overview follows [ElementZoom/Flux-UI-Home-Assistant-Dashboard](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard) (`dashboard/mobile/views/01-overview.yaml`):

| Area | Description |
|------|-------------|
| Hero | Greeting + `weather.forecast_home` |
| Home status | Live chips: lights on count, garage state |
| **Home / Events / Active tabs** | `custom:simple-tabs` filter (ElementZoom reference) |
| **Home tab** | Quick Actions, Climate, Favourite lights |
| **Events tab** | `calendar-card-pro` timeline (or mushroom fallback) |
| **Active tab** | Active now lights + doors open alert (shown when anything is on/open) |
| **Floating music player** | Sonos mini bar above bottom nav; tap opens full player with zone picker |

Config: [`overview_tabs.yaml`](overview_tabs.yaml), [`context.yaml`](context.yaml), [`rooms.yaml`](rooms.yaml), [`media_players.yaml`](media_players.yaml). See [`ROADMAP.md`](ROADMAP.md) for Phase 4.

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
| [thomasloven/lovelace-auto-entities](https://github.com/thomasloven/lovelace-auto-entities) | Active tab — lights currently on |
| [agoberg85/home-assistant-simple-tabs](https://github.com/agoberg85/home-assistant-simple-tabs) | **Home / Events / Active** overview tabs ([ElementZoom ref](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard)) |
| [alexpfau/calendar-card-pro](https://github.com/alexpfau/calendar-card-pro) | Events tab timeline ([ElementZoom ref](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard)) |
| [joseluis9595/lovelace-navbar-card](https://github.com/joseluis9595/lovelace-navbar-card) | Bottom nav + floating music bar |
| [antontanderup/mediocre-hass-media-player-cards](https://github.com/antontanderup/mediocre-hass-media-player-cards) | Full music popup (mushroom fallback) |
| [Clooos/bubble-card](https://github.com/Clooos/bubble-card) | Music player popup shell |
| [maykar/kiosk-mode](https://github.com/maykar/kiosk-mode) | Hide HA header on mobile |
| [Nerwyn/material-you-theme](https://github.com/Nerwyn/material-you-theme) | Full MD3 theming (optional) |
| [Nerwyn/material-you-utilities](https://github.com/Nerwyn/material-you-utilities) | MD3 helpers (optional) |

Garage pulse buttons require [`garage_doors_pulse.yaml`](../garage-doors/packages/garage_doors_pulse.yaml) on HA. **Tapo sensor IDs** are discovered to [`garage-doors/entities.local.yaml`](../garage-doors/entities.local.yaml.example) (gitignored) — icons show open/closed from contact sensors, not button toggles.

### Install Mediocre Media Player Cards (music popup)

Not in the default HACS store — add as a **custom repository**:

1. Open **HACS** → **⋮** (top right) → **Custom repositories**
2. Repository: `https://github.com/antontanderup/mediocre-hass-media-player-cards`
3. Category: **Dashboard** → **Add**
4. **HACS** → **Frontend** → search **Mediocre Hass Media Player Cards** → **Download**
5. **Settings** → **Dashboards** → **⋮** → **Reload resources** (or restart HA)
6. Re-run deploy: `bash home-assistant/scripts/deploy_mac.sh`

Without this, the music popup uses mushroom media player (works, fewer features). Deploy auto-registers the JS if HACS installed it.

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
bash home-assistant/scripts/deploy_mac.sh
```

Or pull latest MD3 branch first:

```bash
bash home-assistant/scripts/deploy_mac.sh --restart-ha
```

Legacy manual deploy:

```bash
bash home-assistant/scripts/run_all_e2e.sh
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
