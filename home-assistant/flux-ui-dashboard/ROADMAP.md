# Flux UI roadmap

## Phase 1 ✅
Overview scaffold, MD3 theme, button-cards, parallel to Mobile Home.

## Phase 2 ✅
Flux navbar (Home/Rooms/Scenes/Camera/More), multi-view dashboard, kiosk-mode header hide.

## Phase 3 ✅ (current)
Context-aware overview + ElementZoom reference layouts.

| Feature | Description |
|---------|-------------|
| **Home status** | Live chips: lights on count, garage door state |
| **Active now** | `auto-entities` — 2-col `flux_light` tiles for lights currently on |
| **Doors open** | Conditional section when any Tapo garage sensor is open |
| **Rooms index** | Large `flux_room` cards in 2-column grid |
| **Room detail** | Status chips + 2-col light toggle tiles (tap toggle, hold more-info) |
| **Favourite lights** | Same 2-col `flux_light` grid as room detail |

Config: [`context.yaml`](context.yaml), [`rooms.yaml`](rooms.yaml)

**HACS required:** `auto-entities`

```bash
python3 home-assistant/flux-ui-dashboard/scripts/verify_phase3.py
bash home-assistant/scripts/run_all_e2e.sh
```

## Phase 4 (next)
- Camera overlay on garage motion
- Media-aware layout (Spotify now playing)
- Material You dynamic colours
- Tablet layout-card dashboard
- Alarm / weather priority header
