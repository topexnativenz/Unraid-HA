# Flux UI roadmap — matching [ElementZoom Flux UI](https://github.com/ElementZoom/Flux-UI-Home-Assistant-Dashboard)

Phase 1 (done): parallel overview with your Mobile Home entities, MD3 theme, button-card tiles, glass styling.

Phase 2 (current): Flux navbar + multi-view dashboard

| Done | Item |
|------|------|
| ✅ | **Flux navbar** — Home, Rooms, Scenes, Camera, More (matches ElementZoom) |
| ✅ | **Views** — overview, rooms, scenes, lights, cameras + room detail pages |
| ✅ | **Navbar on every view** — same pill nav as FB post |
| ⬜ | HACS: navbar-card (required for pill + popups) |
| ⬜ | Material You Theme |
| ⬜ | Kiosk mode HACS installed (hides header on phone) |
| ⬜ | bubble-card light popups |

Install HACS cards then redeploy:

```bash
bash home-assistant/scripts/run_all_e2e.sh
```

Verify Phase 2:

```bash
python3 home-assistant/flux-ui-dashboard/scripts/verify_phase2.py
```

---

Phase 2 (visual polish — remaining):

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
