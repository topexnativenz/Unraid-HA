# Solar dashboard build spec — 332 Three Mile Bush Road

**Status:** Discovery complete → art + entity wiring in progress  
**Site:** 332 Three Mile Bush Road, Te Kamo (Northland, NZ)  
**Quote:** Hubands Energy #31876 (06 May 2026)  
**Tablet:** Landscape 16:9  
**Style:** AI architectural render (photoreal archviz, not drone photo)  
**Retailer:** Contact Energy (Northpower = lines company)  
**Last updated:** 2026-05-26

---

## Background master (LOCKED)

**Owner approval (2026-05-25):** The daytime CGI render is **perfect**. Keep it exactly as it is.

| Rule | Detail |
|------|--------|
| **Frozen asset** | `www/solar-dashboard/backgrounds/v5/master-clear.png` and weather variants built from it (`clear.jpg`, etc.) |
| **Do not change** | No regeneration, re-prompting, colour grading, compositing, pylon paste, ellipse masks, or other edits to the CGI master without your **explicit, subtle** request |
| **Overlays (on request)** | Lovelace card position/styling and baked flow-line geometry — tunable when you ask; master render does not |
| **Always OK** | Entity wiring, demo helpers, deploy paths (e.g. `v5/` cache bust) |
| **Agents / contractors** | Treat the master CGI as read-only; do not rebuild baked art unless you ask |

---

## 1. What you provided

| # | Item | Location |
|---|------|----------|
| 1 | House photos | [Google Drive folder](https://drive.google.com/drive/folders/1Mw41sW6OffbPeVNWUpPvl-xITvfpTMCK?usp=sharing) |
| 2 | Aerial site map | `assets/3MB-Solar-474461e4-62b2-4ef1-a4fd-143772fb8564.png` |
| 3 | Orientation | Landscape wall tablet |
| 4 | Install quote PDF | `Quote_No_31876.pdf` (Hubands / Sigenergy) |
| 5 | Retailer | Northpower |
| 6 | EVs | Model S (Tessie live); Model X before solar go-live — card built for both |
| 7 | Visual | **AI render** (not real photo) + flow lines + brand icons |

---

## 2. Install summary (from quote)

| Component | Spec |
|-----------|------|
| PV | **45 × 460 W** SunPower Performance 7 bi-facial (**20.7 kW** nameplate) |
| Mount | Schletter — **ground mount** (per aerial: array on right boundary) |
| Inverter / controller | **Sigenergy SigenStor** 30 kW Energy Controller |
| Battery | **3 × SigenStor Battery 10.0** (9 kWh usable each → **~27 kWh** usable) |
| EV charger | **Sigenergy Sigen EV DC 25 kW** (7.5 m lead) — in garage area |
| Gateway | Sigenergy HomePro Gateway |
| Supply | **3-phase** |
| Installer | Hubands Energy (10-year install warranty) |

**Not in quote:** separate Tesla Wall Connector — EV charging is **Sigenergy DC charger** + Tessie for vehicle telemetry.

---

## 3. Site layout (aerial → dashboard)

From the annotated aerial (landscape drone view):

```
[ Lawn / 3-phase ]     [ Main house + pool ]     [ Garage / shed ]
                                                      ↑ battery + main board
[ ———————————————————————————————————————————— ground PV array ——→ ]
   (far right, ~45 panels)
```

| Real-world element | Aerial location | Dashboard role |
|--------------------|-----------------|----------------|
| Ground SunPower array | Far **right** | `Roof solar` → rename **`Array`** / **`Solar (ground)`** |
| Main house | Centre | Home load tile |
| Pool | Left of house | Background only (no tile unless desired) |
| Detached garage | **Right** of house | **Battery**, **Sigenergy controller**, **EV charger**, **Model S/X** |
| Switchboard (main) | Garage building | Grid / inverter detail anchor |
| Meter box | House wall | Import/export visual |
| Sub-board | Rear of house | Optional detail |
| 3-phase service | Left lawn area | Grid / Northpower connection |

**Important:** The Serpo-style card uses an **elevated front/side photoreal** view, not top-down. We will pick **one hero camera angle** from your Google Drive photos, then place overlays on that master. The aerial map defines **left-to-right order**: house centre, garage right, panels further right.

---

## 4. Energy flow (directional lines)

Lines are **baked into each of the 5 background JPGs** (same geometry, different sky/light):

| Colour | From | To | Meaning |
|--------|------|-----|---------|
| **Amber / yellow dashed** | Ground PV array | Garage (SigenStor) | Solar production |
| **Amber dashed** | Garage battery | Main house | Battery discharge to load |
| **Amber dashed** | Garage battery ← array | (bidirectional segment) | Charging from solar |
| **White dashed** | Grid / meter direction | Garage or house | Import / export |
| **Green accent** (optional) | Sigenergy EV charger | Model S / X in garage | EV charging when active |

**Live behaviour (phase 2):** When Sigenergy + HA sensors exist, arrow opacity or pulse can follow power direction via `button-card` / CSS (no need for animated GIF backgrounds).

---

## 5. Widget map (target English UI)

| Widget | Entity (live) | Demo until live |
|--------|---------------|-----------------|
| **Tariff** | Contact Energy TOU (`sensor.contact_tariff_*`) | Peak 7am–9pm 33.5c, off-peak 16.5c; Northpower = network only |
| **Solar forecast** | Forecast.Solar or Sigenergy | `sensor.solar_forecast_*` |
| **Grid use** | Sigenergy import W | `sensor.grid_import_power` |
| **Solar (ground)** | Sigenergy PV W | `sensor.solar_ground_power` |
| **Home use** | Calculated load W | `sensor.home_consumption_power` |
| **Battery** | SigenStor SOC / power / V | `sensor.solar_battery_*` |
| **Garage — Model S** | Tessie | `sensor.garage_model_s_*` |
| **Garage — Model X** | Tessie (when added) | `sensor.garage_model_x_*` (demo 72%) |
| **EV charger** | Sigenergy charger kW | TBD integration |
| **Grid details** | Voltage, temp, cycles | Existing templates |
| **Bottom row** | Today / month / year kWh | Existing templates |

Rename misleading **`Roof solar`** → **`Solar array`** (all panels are ground-mounted).

---

## 6. Premium brand assets

Store under `/config/www/solar-dashboard/icons/` (repo: `www/solar-dashboard/icons/`):

| Asset | Use | Source |
|-------|-----|--------|
| `sigenergy-logo.png` | Battery / controller card | Sigenergy media kit or installer |
| `sunpower-logo.png` | Array / PV total tile | SunPower partner assets |
| `tesla-model-s.png` | Garage row (silhouette or small photo) | Tessie / official Tesla press (non-commercial) |
| `tesla-model-x.png` | Garage row (placeholder until vehicle) | Same |
| `sigen-ev-charger.png` | Charger status near garage | Hubands / Sigenergy |
| `northpower.png` | Tariff card (optional) | Northpower brand guidelines |

**UI rule:** Brand icons at **24–32 px** in card headers; no stretched logos. Use `button-card` `custom_fields` with `<img src="/local/solar-dashboard/icons/...">` beside values.

---

## 7. Background pipeline (v5 AI render)

**Rejected:** v3 drone aerial (neighbours visible, not Serpo-style).

**Approved (LOCKED):** Closer **elevated 3/4 archviz** of property only (inside orange boundary on site map). Reference photos: house (`-2.jpg`), garage (`-14.jpg`, `-15.jpg`). Master: `backgrounds/v5/master-clear.png` (AI-generated daytime CGI — see **Background master (LOCKED)** above).

### Steps

1. **Do not regenerate the master** without explicit user art direction (see **Background master (LOCKED)**).
2. Rebuild weather JPGs only if you explicitly request line-geometry changes (`scripts/build_v4_backgrounds.py` → `backgrounds/v5/`).
3. Dashboard uses `/local/solar-dashboard/backgrounds/v5/*.jpg`.
4. Tune `placement-map.yaml` on tablet once.

**Scene must include:** main house + pool (left), open garage with **Model S + Model X**, **45-panel ground array** (right lawn), Sigenergy battery on garage wall, 3-phase pole (left), no neighbouring properties.

---

## 8. Home Assistant integration plan

| Phase | When | Work |
|-------|------|------|
| **Now** | Pre-install | Tessie Model S, demo solar, Model X placeholder, Contact TOU, **v5 AI render (LOCKED)** |
| **Install day** | Hubands commission | Sigenergy app + HomePro Gateway on LAN; check for HA integration / Modbus / API |
| **Go-live** | Export meter active | Map Sigenergy entities → package `input_text` helpers; demo off |
| **Model X** | Before go-live (your plan) | Update `input_text.tessie_model_x_*` in HA |

**Sigenergy in HA:** Confirm with Hubands whether SigenStor exposes **local API**, **Modbus**, or cloud-only. If no integration exists at install, use **REST/MQTT bridge** or manual template sensors from Sigenergy app export until official integration lands.

---

## 9. Northpower (tariff tile)

Replace French RTE Tempo dots with **Northpower-relevant** display:

- **Today / tonight** plan indicator (e.g. standard vs controlled if applicable)
- Optional: **buy** / **sell** rate when you have plan details
- Import/export from Sigenergy when live

**Need from you:** Northpower plan name (e.g. Standard, User Plan) and whether you have **buy-back / export** rates for display.

---

## 10. Implementation steps (ordered)

| Step | Task | Owner | Done |
|------|------|-------|------|
| 1 | Sync Google Drive photos to repo `source-photos/` | You / agent | ☐ |
| 2 | Choose hero camera angle | You approve | ☐ |
| 3 | AI render + flow arrows (`v4/`) | `scripts/build_v4_backgrounds.py` | ☑ |
| 4 | Write `placement-map.yaml` for 332 3MB layout | Agent | ☐ |
| 5 | Update Lovelace: English labels, array rename, Northpower tile | Agent | ☐ |
| 6 | Add brand icon folder + garage card with logos | Agent | ☐ |
| 7 | Register Forecast.Solar with **20.7 kW** + panel tilt/orientation | Agent | ☐ |
| 8 | Pre-wire Sigenergy entity map (stub `input_text`) | Agent | ☐ |
| 9 | Deploy + tablet test (landscape 16:9) | You | ☐ |
| 10 | At install: map live Sigenergy + Northpower export | Agent + you | ☐ |
| 11 | Add Model X Tessie IDs when vehicle arrives | You | ☐ |

---

## 11. Immediate blockers

1. **Google Drive photos** — agent cannot read the folder directly; need local copy in repo or Samba sync.
2. **Sigenergy HA entity list** — unknown until gateway is on-site (stub now, map later).
3. **Northpower rate details** — optional for tariff tile copy.

---

## 12. File references

| File | Purpose |
|------|---------|
| `placement-map.yaml` | Widget % positions (created next) |
| `packages/solar_dashboard.yaml` | Demo / live solar templates |
| `packages/solar_dashboard_ev.yaml` | Tessie garage |
| `lovelace/dashboards/solar_dashboard.yaml` | Active dashboard |
| `assets/3MB-Solar-*.png` | Aerial site map |
