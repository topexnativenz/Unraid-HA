# Tablet dashboard (Home Assistant)

Dark **glassmorphism** wall/tablet dashboard inspired by modern kiosk UIs: weather & time, system status, 4-day forecast, person pills, scene shortcuts, room navigation, camera placeholders, and a floating bottom nav bar.

Designed for **landscape tablets** (Fully Kiosk, WallPanel, iPad kiosk). Matches the reference layout: rounded glass cards, gradient accent pills, 2×2 camera grid.

**Demo mode (default ON)** provides template entities and static placeholder imagery so the dashboard looks complete while awaiting solar install and live integrations.

## What you get

| File | Purpose |
|------|---------|
| `lovelace/dashboards/tablet_dashboard.yaml` | Main dashboard (panel view + grid layout) |
| `lovelace/includes/*.yaml` | Zone cards (weather, status, people, scenes, cameras, nav) |
| `lovelace/includes/tablet_templates.yaml` | Shared `button-card` templates |
| `lovelace/includes/entity_map.yaml` | Demo ↔ live entity mapping reference |
| `packages/tablet_dashboard.yaml` | Status-count template sensors + helpers |
| `packages/tablet_demo.yaml` | Demo mode entities, scene buttons, automations |
| `themes/tablet_glass.yaml` | Dark glass theme (`tablet_glass`) |
| `www/tablet-dashboard/*` | CSS, camera placeholders, avatars, radar image |
| `scripts/generate_placeholders.py` | Regenerate placeholder JPG/PNG assets |
| `scripts/deploy_tablet_dashboard.py` | Automated deploy to HA |

## Prerequisites (HACS)

Install from [HACS](https://hacs.xyz/):

| Custom card | Why |
|-------------|-----|
| [button-card](https://github.com/custom-cards/button-card) | Weather hero, status chips, person pills, scenes, nav |
| [card-mod](https://github.com/thomasloven/lovelace-card-mod) | Glass blur, typography, camera styling |
| [layout-card](https://github.com/thomasloven/lovelace-layout-card) | Responsive grid (weather / status / scenes / cameras) |
| [stack-in-card](https://github.com/custom-cards/stack-in-card) | Optional grouping (cameras zone) |
| [Mushroom Cards](https://github.com/piitaya/lovelace-mushroom) | Recommended on your instance; not required for this dashboard |

## Install

### Option A — Automated deploy

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/tablet-dashboard/scripts/deploy_tablet_dashboard.py
```

Then open **http://192.168.1.239:8123/tablet-dashboard/home**

### Option B — Manual copy

```bash
# Packages (status sensors + demo entities)
cp /Users/topexnative/Projects/unraid-array-design/home-assistant/tablet-dashboard/packages/tablet_dashboard.yaml \
   /config/packages/tablet_dashboard.yaml
cp /Users/topexnative/Projects/unraid-array-design/home-assistant/tablet-dashboard/packages/tablet_demo.yaml \
   /config/packages/tablet_demo.yaml

# Theme
cp /Users/topexnative/Projects/unraid-array-design/home-assistant/tablet-dashboard/themes/tablet_glass.yaml \
   /config/themes/tablet_glass.yaml

# Dashboard + includes
mkdir -p /config/dashboards/includes
cp /Users/topexnative/Projects/unraid-array-design/home-assistant/tablet-dashboard/lovelace/dashboards/tablet_dashboard.yaml \
   /config/dashboards/tablet_dashboard.yaml
cp /Users/topexnative/Projects/unraid-array-design/home-assistant/tablet-dashboard/lovelace/includes/*.yaml \
   /config/dashboards/includes/

# Web assets (placeholders + CSS)
mkdir -p /config/www/tablet-dashboard
cp -r /Users/topexnative/Projects/unraid-array-design/home-assistant/tablet-dashboard/www/tablet-dashboard/* \
   /config/www/tablet-dashboard/
```

Ensure `configuration.yaml` loads packages and themes:

```yaml
homeassistant:
  packages: !include_dir_named packages

frontend:
  themes: !include_dir_merge_named themes

lovelace:
  mode: storage
  dashboards:
    tablet-dashboard:
      mode: yaml
      filename: dashboards/tablet_dashboard.yaml
      title: Tablet
      icon: mdi:tablet-dashboard
      show_in_sidebar: true
```

Reload **Template entities**, **Automations**, **Themes**, restart HA if new helpers were added, and refresh the browser cache.

## Demo mode

| Helper | Default | Purpose |
|--------|---------|---------|
| `input_boolean.tablet_demo_mode` | **ON** | When ON, status counts show reference values (9 lights, 1 lock, 12 shades, 2 alarms, 15 occupancy). When OFF, counts come from live HA entities. |

The dashboard YAML currently points at **demo template entities** for weather, people, climate, vacuum, media, scenes, and static camera images. Demo scene buttons fire `persistent_notification` toasts.

### Disable demo mode (post-solar-install checklist)

1. **Settings → Devices & Services → Helpers** → turn off **Tablet Demo Mode**
2. Edit `lovelace/includes/zone_*.yaml` (or `/config/dashboards/includes/` after deploy) and swap entity IDs using the table below
3. Re-run deploy or reload Lovelace
4. Replace camera `picture-entity` cards with live `picture-glance` + `camera.*` entities
5. Optionally delete or disable `packages/tablet_demo.yaml` once no longer needed

### Demo entity list

| Entity | Type | Demo value |
|--------|------|------------|
| `input_boolean.tablet_demo_mode` | helper | ON (default) |
| `sensor.tablet_demo_weather` | template | 82°F Sunny, humidity 24%, wind 8 mph, 4-day forecast |
| `sensor.tablet_demo_uv_index` | template | 2 (Low) |
| `sensor.tablet_demo_person_david` | template | David, 65% battery, Home • 4 hours ago |
| `sensor.tablet_demo_person_genna` | template | Genna, 80% battery, Home • 25 mins ago |
| `sensor.tablet_demo_vacuum` | template | RoboVacs idle |
| `sensor.tablet_demo_climate` | template | 72°F thermostat |
| `sensor.tablet_demo_media` | template | Media idle |
| `input_button.tablet_demo_scene_guest` | helper | Guest scene toast |
| `input_button.tablet_demo_scene_dim` | helper | Dim scene toast |
| `input_button.tablet_demo_scene_movie` | helper | Movie scene toast |
| `input_button.tablet_demo_scene_night` | helper | Night scene toast |
| `input_button.tablet_demo_scene_vaca` | helper | Vaca scene toast |
| `sensor.tablet_lights_on_count` | template | 9 when demo mode ON |
| `sensor.tablet_locks_open_count` | template | 1 when demo mode ON |
| `sensor.tablet_shades_open_count` | template | 12 when demo mode ON |
| `sensor.tablet_alarms_active_count` | template | 2 when demo mode ON |
| `sensor.tablet_occupancy_on_count` | template | 15 when demo mode ON |

### Placeholder assets (`/local/tablet-dashboard/`)

| File | Purpose |
|------|---------|
| `camera-backyard.jpg` | Backyard camera tile |
| `camera-front-yard.jpg` | Front yard camera tile |
| `camera-driveway.jpg` | Driveway camera tile |
| `camera-porch.jpg` | Porch camera tile |
| `avatar-david.png` | David profile circle |
| `avatar-genna.png` | Genna profile circle |
| `radar-placeholder.png` | Weather radar accordion |
| `tablet-glass.css` | Full-bleed dark background + forecast bar styles |

Regenerate placeholders:

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/tablet-dashboard/scripts/generate_placeholders.py
```

## Entity mapping (demo → live)

See `lovelace/includes/entity_map.yaml` for the full reference.

### Weather & time

| UI element | Demo entity | Live entity |
|------------|-------------|-------------|
| Temperature, condition, forecast | `sensor.tablet_demo_weather` | `weather.forecast_home` |
| Humidity / wind / precip | `sensor.tablet_demo_weather` attributes | `weather.forecast_home` attributes |
| UV Index | `sensor.tablet_uv_index` | Same (reads live UV when demo mode OFF) |

### Status row

| UI label | Sensor | Notes |
|----------|--------|-------|
| Light | `sensor.tablet_lights_on_count` | Demo: 9; live: counts `light.*` |
| Lock | `sensor.tablet_locks_open_count` | Demo: 1 |
| Shade | `sensor.tablet_shades_open_count` | Demo: 12 |
| Alarm | `sensor.tablet_alarms_active_count` | Demo: 2 |
| Occupancy | `sensor.tablet_occupancy_on_count` | Demo: 15 |

### People & quick controls

| UI element | Demo entity | Live entity |
|------------|-------------|-------------|
| Person 1 | `sensor.tablet_demo_person_david` | `person.david` + battery sensor |
| Person 2 | `sensor.tablet_demo_person_genna` | `person.genna` + battery sensor |
| RoboVacs | `sensor.tablet_demo_vacuum` | `vacuum.saros_10` |
| Climate | `sensor.tablet_demo_climate` | `climate.main_thermostat` |
| Media | `sensor.tablet_demo_media` | `media_player.kitchen_sonos` |

### Scenes

| Button | Demo entity | Live entity |
|--------|-------------|-------------|
| Guest | `input_button.tablet_demo_scene_guest` | `scene.guest` |
| Dim | `input_button.tablet_demo_scene_dim` | `scene.dim` |
| Movie | `input_button.tablet_demo_scene_movie` | `scene.movie` |
| Night | `input_button.tablet_demo_scene_night` | `light.night_arrival` or `scene.night_arrival` |
| Vaca | `input_button.tablet_demo_scene_vaca` | `scene.vacation` |

### Cameras

| Tile | Demo (static image) | Live entity |
|------|---------------------|-------------|
| Backyard | `/local/tablet-dashboard/camera-backyard.jpg` | `camera.backyard` |
| Front Yard | `/local/tablet-dashboard/camera-front-yard.jpg` | `camera.front_yard` |
| Driveway | `/local/tablet-dashboard/camera-driveway.jpg` | `camera.driveway` |
| Porch | `/local/tablet-dashboard/camera-porch.jpg` | `camera.garage_door` |

### Bottom navigation (`zone_nav.yaml`)

| Icon | Path | Notes |
|------|------|-------|
| Home | `/tablet-dashboard/home` | This dashboard |
| Audio | `/dashboard-music` | Your music dashboard |
| Camera | `/mobile-home/cameras` | Mobile Home cameras tab |
| Sprinkler | `/tablet-dashboard/home` | **MAP** to irrigation dashboard |
| Security | `/tablet-dashboard/home` | **MAP** to alarm / lock dashboard |
| Floorplan | `/tablet-dashboard/home` | **MAP** to floorplan view |
| Energy | `/solar-dashboard` | Solar dashboard (deployed) |
| Voice | `/tablet-dashboard/home` | **MAP** to Assist / intercom |

## Tablet / kiosk tips

- Dashboard **⋮ → Theme → Tablet Glass**
- **Settings → Dashboards → Tablet → ⋮ → Hide sidebar** (or profile → kiosk)
- **Fully Kiosk Browser** on Android: full-screen, motion wake, `/tablet-dashboard/home` as start URL
- Target resolution: **1920×1080** landscape; layout collapses to single column below 900px width

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `custom:button-card` / `layout-card` error | Install HACS cards; run deploy script to register resources |
| Blank person photos | Confirm `/local/tablet-dashboard/avatar-*.png` deployed; hard-refresh browser |
| Cameras show broken image | Run `generate_placeholders.py` and redeploy www assets |
| Status counts stuck at demo values | Turn off `input_boolean.tablet_demo_mode` |
| Scene buttons do nothing | Check automations loaded from `tablet_demo.yaml` |
| Theme not listed | Copy `tablet_glass.yaml` to `/config/themes/`, reload themes |
| Includes not found after deploy | Ensure `includes/` copied to `/config/dashboards/includes/` |

## Layout reference

```
┌─────────────────┬──────────────────────────────┐
│ Weather + Time  │ Status row + 4-day forecast  │
│ Humidity UV…    │ Weather radar accordion      │
├─────────────────┴──────────────────────────────┤
│ Person pills │ RoboVac │ Climate │ Media       │
├────────────────────┬───────────────────────────┤
│ Scenes + floor +   │ 2×2 camera grid + FAB     │
│ room list          │                           │
├────────────────────┴───────────────────────────┤
│        Floating nav pill (8 icons)             │
└────────────────────────────────────────────────┘
```
