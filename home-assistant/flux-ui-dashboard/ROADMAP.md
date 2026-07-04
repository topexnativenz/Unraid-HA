# Flux UI roadmap — matching [ElementZoom Flux UI](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard)

Phase 1 (done): parallel overview with your Mobile Home entities, MD3 theme, button-card tiles, glass styling.

Phase 2 (next — visual polish): what makes it look like the FB post without rebuilding the whole framework.

| Step | What | Why it matters |
|------|------|----------------|
| 2a | Install HACS cards (see below) | Fixes Configuration error, enables pill nav + popups |
| 2b | Material You Theme | Dynamic accent colours per user — core Flux look |
| 2b | Kiosk Mode | Hide HA header/sidebar on phone for app-like UI |
| 2c | Redeploy after HACS | navbar-card, bubble-card, layout-card registered |
| 2d | Profile → theme `flux-ui-md3` | Purple wallpaper + MD3 tokens on all cards |

### HACS to install now (biggest visual jump)

1. [navbar-card](https://github.com/joseluis9595/lovelace-navbar-card) — floating pill bottom nav (fixes red Configuration error)
2. [Material You Theme](https://github.com/Nerwyn/material-you-theme) — Material You colours
3. [bubble-card](https://github.com/Clooos/bubble-card) — light/scene popups with sliders
4. [layout-card](https://github.com/thomasloven/lovelace-layout-card) — tablet multi-column layouts
5. [kiosk-mode](https://github.com/maykar/kiosk-mode) — hide chrome on `/flux-ui/*`

Then redeploy:

```bash
bash home-assistant/scripts/run_all_e2e.sh
```

---

Phase 3 (Flux framework features): what the full ElementZoom repo adds beyond styling.

- **Context-aware overview** — open doors/windows, active lights, running appliances appear only when relevant
- **Live camera overlays** — garage motion shows camera + timer inline
- **Media-aware layout** — tablet swaps sections when Spotify is playing
- **Room views** — per-room state, curtains, climate
- **Shared YAML partials** — `dashboard/shared/` templates used by mobile + tablet
- **Tablet dashboard** — separate layout with layout-card grids
- **Alarm / weather priority header** — mobile header changes for alerts

These require porting or adapting ElementZoom's YAML architecture and mapping your entities — not just theme tweaks.

---

Phase 4 (optional integrations from Flux custom-cards.md)

- Clock Weather Card, mini-graph-card, apexcharts for climate/history
- WebRTC camera cards
- Auto-entities for dynamic "what's open" lists
- Tessie / media cards (you already have Tesla tab on Mobile Home)

---

## Current gaps vs FB screenshots

| You have now | FB Flux post |
|--------------|--------------|
| Greeting + action tiles | Same, plus richer hero animations |
| Flat dark cards | Glass blur + wallpaper (needs card-mod + theme reload) |
| Static sections | Context-aware sections that show/hide |
| Configuration error (navbar) | Floating pill nav |
| Climate fallback | Live climate graphs from Mobile Home |
| No popups | Bubble card light/scene controls |
| HA header visible | Kiosk / full-bleed mobile |

---

## Quick wins after HACS install

1. Hard-refresh or reset HA app cache
2. Set default dashboard to Flux UI on phone (Profile → Dashboard)
3. Set theme to `flux-ui-md3` or Material You
4. Confirm deploy log: `sections=5`, no Configuration error
