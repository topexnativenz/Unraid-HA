# Flux UI roadmap

## Phase 1 ✅
Overview scaffold, MD3 theme, button-cards, parallel to Mobile Home.

## Phase 2 ✅
Flux navbar (Home/Rooms/Scenes/Camera/More), multi-view dashboard, kiosk-mode header hide.

## Phase 3 ✅ (current)
Context-aware overview + bubble light popups.

| Feature | Description |
|---------|-------------|
| **Home status** | Live chips: lights on count, garage door state |
| **Active now** | `auto-entities` — only lights currently on (hidden when none) |
| **Doors open** | Conditional section when any Tapo garage sensor is open |
| **Bubble popups** | Tap a light tile → slider popup (bubble-card + mushroom light) |

Config: [`context.yaml`](context.yaml)

**HACS required:** `auto-entities`, `bubble-card`

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
