# G-UNIT 16:9 — Casa Luna wall tablet (1920×1080)

Parallel install of the **G-UNIT** energy + home dashboard for the SmartHome **15.6" 1920×1080** wall tablet. Does **not** replace the original **3:2 (1500×1000)** dashboard in [`casa-luna/`](../casa-luna/).

| Dashboard | Canvas | URL | Sidebar |
|-----------|--------|-----|---------|
| G-UNIT (3:2) | 1500×1000 | http://192.168.1.239:8123/casa-luna/home | **G-UNIT** |
| **G-UNIT 16:9** | **1920×1080** | http://192.168.1.239:8123/g-unit-16x9/home | **G-UNIT 16:9** |

Same entity bindings as `casa_luna.yaml`. Packages (`casa_luna_demo.yaml`, `casa_luna_entities.yaml`) are shared copies — deploy is idempotent if already present from the 3:2 install.

## What you get

| File | Purpose |
|------|---------|
| `www/community/casa-luna-16x9/casa-luna.js` | Custom Lovelace card `custom:casa-luna-16x9` (build 16x9-7) |
| `www/community/casa-luna-16x9/sky/*.png` | 13 weather × time sky backgrounds (same assets as 3:2) |
| `lovelace/patches/floorplan_4_3_gunit_backlink.yaml` | Floorplan (4:3) moon icon → G-UNIT 16:9 (WebSocket patch) |
| `lovelace/dashboards/casa_luna_16x9.yaml` | Panel dashboard + entity bindings |
| `scripts/scale_casa_luna_16x9.py` | Regenerate JS geometry from `casa-luna/casa-luna.js` |
| `scripts/deploy_casa_luna_16x9.py` | SMB + WebSocket deploy |

## Geometry

Canvas: **1920×1080** (`VB_W` / `VB_H`).

| Axis | Scale factor | Source |
|------|--------------|--------|
| X | ×1.28 | 1920 ÷ 1500 |
| Y | ×1.08 | 1080 ÷ 1000 |

**Scaled automatically:** entire `SL.*` slot object (nav, battery cylinder, stat row, inverter blocks, bottom tiles, arc anchor coords), detail panel box, header/weather hotspots, sun arc layer position/size, flow overlay height, battery/grid flow anchor Y and `POLE_P_X`, `ResizeObserver` (width-fit when viewport ≈16:9, else `min(w,h)`).

**Panel fill (16x9-3):** `.stage` uses `height:100%` (not `aspect-ratio`) so the card fills the kiosk viewport; `card_mod` + `panel-kiosk-fix.js` zero HA wrapper padding. At native 1920×1080, width-based scale = 1.0 with no bottom bars.

**Left in arc SVG viewBox space (scale via container):** sun/moon bezier path, PV wave path endpoints (`278,341`), rise/set label positions — the arc `<svg>` is stretched proportionally with `preserveAspectRatio="xMidYMid meet"`.

**Sky PNGs:** `object-fit: cover` on `.bg` — same 3:2-ish sky art crops slightly differently on 16:9; acceptable without re-authoring assets.

## Install / deploy

Regenerate JS (after upstream `casa-luna.js` changes):

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/casa-luna-16x9/scripts/scale_casa_luna_16x9.py
```

Deploy to HA (restarts core so new `lovelace:` dashboard registration loads):

```bash
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/casa-luna-16x9/scripts/deploy_casa_luna_16x9.py
```

Skip restart if you only changed JS/assets and will reload manually: `--skip-restart`.

Hard-refresh after deploy: `Cmd + Shift + R`.

## Wall tablet setup

1. Log the **15.6" panel** in as **`panel`** (or dedicated user).
2. **Profile → Dashboard** → **G-UNIT 16:9** (not the 3:2 **G-UNIT**).
3. **Set as default on this device**.
4. Open http://192.168.1.239:8123/g-unit-16x9/home

The existing 3:2 G-UNIT remains at `/casa-luna/home` for other tablets.

**Floorplan (4:3) moon backlink:** top-left icon on `/floorplan-4-3/ground-floor` navigates to `/g-unit-16x9/home` (not the 3:2 dashboard). **Lighting** nav on G-UNIT 16:9 still opens `/floorplan-4-3/ground-floor`. Deploy applies the backlink via WebSocket on every run.

## Flow line nudge (16x9-2, superseded)

Build 16x9-2 extended C→D dash counts (2→6) to reach the house — wrong approach for the mirrored battery path. See **16x9-5** for the correct fix.

## Bottom letterboxing fix (16x9-3)

**Root cause:** build 16x9-2 sized `.stage` with `aspect-ratio:16/9` and uniform `min(w,h)` scale. The HA panel wrapper is full viewport height; the aspect-ratio box was shorter than the container, leaving black bars at the bottom.

**Fix:** `.stage` → `height:100%`; `card_mod` on the dashboard card → `100vh` host; `panel-kiosk-fix.js` → zero view padding + `/g-unit-16x9` path; `ResizeObserver` → width-fit when viewport aspect ≈16:9 (scale = 1.0 at native 1920×1080).

## Energy flow restore (16x9-5)

**What was wrong in 16x9-4:** `BATT_HOUSE_JX` used **765** (a stale guess) instead of the actual 3:2 computed junction **825**. That pulled the battery C→D horizontal 77px short of the scaled house entry (`979` vs correct `1056`), making the right-side flow look missing or misaligned. Grid `POLE_HOUSE_JX` at 568→727 was correct but the ad-hoc `FLOW_SX` hack layer replaced the original formula structure instead of scaling from computed anchors.

**Fix (16x9-5):** `scale_casa_luna_16x9.py` now computes the full 3:2 anchor table in Python, scales house junction X with `×1.28`, and derives C→D segment lengths from bend corners. Grid stays **LEFT** (`POLE_P_X`→`POLE_D_X`), battery stays **RIGHT** (`BATT_A_X`→`BATT_D_X`). Dash pixel sizes unchanged; only anchor coordinates scale.

| Anchor | 1500×1000 | 1920×1080 (16x9-5) | Role |
|--------|-----------|---------------------|------|
| `POLE_P_X` | 358 | **431** | Grid flow start (left / pole) |
| `POLE_Q_X` | 514 | **587** | Grid corner before vertical |
| `POLE_D_X` | 568 | **727** | Grid → house junction (left side) |
| `POLE_Y` | 386 | **419** | Grid flow row |
| `BATT_A_X` | 1113 | **1425** | Battery flow start (cylinder edge) |
| `BATT_B_X` | 879 | **1191** | Battery corner before vertical |
| `BATT_D_X` | 825 | **1056** | Battery → house junction (right side) |
| `BATT_Y` | 351 | **381** | Battery flow row |

`flowOverlay` keeps `viewBox="0 0 1920 1080"` + `z-index:8` from 16x9-4 (paths paint above right-column tiles). Letterboxing fix from 16x9-3 unchanged.

## Battery cylinder fit (16x9-7)

**What was wrong in 16x9-6:** viewBox `34 117 100 172` + inset `3px 5px` left only ~6–7px below the base ellipse (art y=287). The `.box` `border-radius:14px` + `overflow:hidden` on `.cyl-widget` still clipped the bottom collar/groove at the widget corners — worse when the stage is width-fit scaled on the panel.

**Fix (16x9-7):** viewBox → `32 114 104 178` (more padding around art); SVG inset → `5px 8px 14px 8px` (extra 14px bottom for corner radius); CSS `transform:scale(0.88)` with `transform-origin:50% 45%` on `.cyl-widget > svg`. Liquid fill / clip paths unchanged (same SVG user-space coords).

| | 16x9-6 (before) | 16x9-7 (after) |
|--|-----------------|----------------|
| viewBox | 34 117 100 172 | **32 114 104 178** |
| SVG inset | 3px 5px | **5px 8px 14px 8px** |
| CSS scale | none | **0.88** @ 50% 45% |
| Art bottom margin (container px) | ~7px | **~41px** |
| Effective art height (container px) | ~297 | **~246** |

`r_cyl` unchanged: `{1425, 99, 195, 311}`.

## Battery cylinder fit (16x9-6, superseded)

**What was wrong in 16x9-5:** `SL.r_cyl` scaled to `{1425, 99, 195, 311}` but the cylinder SVG kept the 3:2 viewBox `34 118 100 168`. On 16:9 the container aspect (195÷311 ≈ 0.627) is wider than the viewBox (100÷168 ≈ 0.595), so `preserveAspectRatio="meet"` height-fills the widget. That pushed the bottom base (SVG y=287, 1 unit past the viewBox) to ~313px — **~2px clipped** by `overflow:hidden`. Top nub had only ~2px clearance.

**Fix (16x9-6):** viewBox → `34 117 100 172` (includes full cap + base art); SVG inset `3px 5px` inside `.cyl-widget` for border-radius clearance; `.cyl-widget > svg { overflow:hidden }`. Liquid fill / clip paths unchanged (same SVG user-space coords). `r_stats` / `r_mode` positions unchanged (12px gap at x=1620→1632).

| | 3:2 (1500×1000) | 16:9 (16x9-6) |
|--|-----------------|---------------|
| `r_cyl` | 1113, 92, 152, 288 | 1425, 99, 195, 311 |
| viewBox | 34 118 100 168 | **34 117 100 172** |
| Scale mode | width-limited (16px vertical pad) | height-limited with inset (fits inside border) |

## Known visual follow-ups

- Bottom tile row is tight at y≈990 on 1080px canvas (~9px margin); fine on panel but watch for font overflow on long UniFi labels.
- Header **G-UNIT** metallic title letter-spacing unchanged — may feel slightly sparse on wider canvas.
- Regenerate geometry whenever `home-assistant/casa-luna/www/community/casa-luna/casa-luna.js` changes materially.

## Do not edit

- `home-assistant/casa-luna/` (3:2 G-UNIT)
- `home-assistant/solar-dashboard/`
