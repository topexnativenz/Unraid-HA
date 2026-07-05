# Flux UI roadmap

## Phase 1 ✅
Overview scaffold, MD3 theme, button-cards, parallel to Mobile Home.

## Phase 2 ✅
Flux navbar (Home/Rooms/Scenes/Camera/More), multi-view dashboard, kiosk-mode header hide.

## Phase 3 ✅
Context-aware overview + ElementZoom reference layouts.

| Feature | Description |
|---------|-------------|
| **Home / Events / Active tabs** | `custom:simple-tabs` — [ElementZoom reference](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard) |
| **Home tab** | Quick Actions, Climate, Favourite lights |
| **Events tab** | `calendar-card-pro` timeline (config: `overview_tabs.yaml`) |
| **Active tab** | Auto-entities lights + doors open (conditional visibility) |
| **Home status** | Live chips: lights on count, garage door state |
| **Doors open** | Conditional strip inside Active tab when Tapo garage sensor is open |
| **Rooms index** | Large `flux_room` cards — temp/humidity label, sensor column, 2-col grid |
| **Room detail** | Status chips, feature row, sub-nav tabs, light count badge, 2-col lights |
| **Room grid subview** | 3-col dense light grid + shortcuts per room |
| **Room camera subview** | Per-room camera feeds from `cameras.yaml` / `rooms.yaml` |
| **Favourite lights** | Same 2-col `flux_light` grid as room detail |
| **Scenes tab** | Quick scripts + HA `scene.*` auto-discovery |
| **Lights tab** | Active now + favourites + all room groups + Upstairs/Outside |
| **Cameras tab** | `picture-glance` feeds + camera auto-discovery |

Config: [`context.yaml`](context.yaml), [`overview_tabs.yaml`](overview_tabs.yaml), [`rooms.yaml`](rooms.yaml), [`scenes.yaml`](scenes.yaml), [`cameras.yaml`](cameras.yaml), [`light_groups.yaml`](light_groups.yaml)

**HACS required:** `auto-entities`, `simple-tabs`  
**HACS optional:** `calendar-card-pro` (Events timeline — ElementZoom reference)

```bash
python3 home-assistant/flux-ui-dashboard/scripts/verify_phase3.py
python3 home-assistant/flux-ui-dashboard/scripts/verify_completeness.py
bash home-assistant/scripts/run_all_e2e.sh
```

## Phase 4 (next)
- Camera overlay on garage motion
- Media-aware layout (Spotify now playing)
- Material You dynamic colours
- Tablet layout-card dashboard
- Alarm / weather priority header
- Wire room feature row entities (Presence / Movie / Adaptive)
- Populate `room_sensors.yaml` via live discovery
