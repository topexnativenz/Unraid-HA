# Physical Magnetic Levitation Globe (Iron Man / Jarvis)

You asked for a **real floating globe** — not a web animation. This guide covers what to buy, DIY options, and how to tie it into your Jarvis assistant (voice states → LED ring on the base).

## What you actually want

In Iron Man, the desk pieces are usually:

| Movie element | Real-world equivalent |
|---------------|----------------------|
| Arc Reactor (floating, glowing) | **Levitating Arc Reactor replica** — electromagnetic base, ~$90–120 |
| Holographic Earth / data sphere | **C‑base magnetic levitation globe** — 3–8" sphere floats + spins, LED ring in base |
| Jarvis HUD on screen | Your **software UI** (optional companion — not a substitute for the physical float) |

There is no off-the-shelf product that is *exactly* the movie hologram. The closest **physical** look is:

1. **Levitating Arc Reactor** (most “Tony Stark desk”)
2. **Magnetic levitation globe** (floating world ball + RGB base)
3. **Custom build**: levitation module + 3D‑printed orange wireframe shell + addressable LED ring

---

## Option A — Buy ready-made (fastest)

### 1. Levitating Arc Reactor (most Iron Man)

- Search: *“MK1 arc reactor magnetic levitation”* or *“floating arc reactor desk”*
- Vendors: EngineDIY, various Amazon/AliExpress listings
- **Pros:** Looks like the film; induction power; spins in mid-air  
- **Cons:** Not a “globe” — it’s the reactor disc

### 2. C‑shape magnetic levitation globe

- Search: *“magnetic levitating globe C shape RGB”*
- Sphere ~3.3"–8" (8–20 cm); map-printed or plain black/gold ball
- Base has **RGB LEDs** around the C‑arm
- **Pros:** Actual floating globe; easy to find (~$40–100 USD)  
- **Cons:** Earth map, not orange wireframe — you customize the ball or add a sleeve

### 3. Plain black/gold floating ball + custom shell

Buy a **black levitating globe** (no map), 3D‑print or buy an **orange wireframe icosahedron shell** that clips over the ball (lightweight PLA). Keeps levitation working if total float weight stays under the module’s limit (usually **≤200–350 g** depending on module).

---

## Option B — DIY Jarvis globe (best match + smart home)

### Shopping list (approximate)

| Part | Notes | ~USD |
|------|--------|------|
| Magnetic levitation module (C‑base or disc) | 350–500 g load, 12 V | 25–45 |
| Hollow foam/PLA sphere 80–100 mm | Paint orange or wireframe print | 5–15 |
| WS2812B LED ring 60 mm or 74 mm | 24–32 LEDs, 5 V | 5–10 |
| ESP32 dev board | Wi‑Fi, MQTT / ESPHome | 5–8 |
| 5 V PSU (2 A+) | For LEDs | 5 |
| **Optional** thin orange acrylic / PETG wireframe | Snap over sphere | DIY |

**Tools:** soldering iron, USB cable, calipers to balance float height.

### Levitation tips

1. Use the **balance spoon/tool** included with the base — find the float point before powering LEDs.
2. Keep **top weight centered**; LED ring stays on the **base**, not on the floating ball (easier).
3. First float **without** shell; add shell gradually if you wrap the ball.
4. Module must stay **level**; vibration (subwoofer, desk bumps) drops the ball.

---

## Tie it to Jarvis (Home Assistant)

Use the included package so your **voice assistant state** drives the **base LED ring** (orange idle → brighter gold listening → pulse speaking).

### 1. Flash ESPHome on ESP32

Create `jarvis/physical/esphome/jarvis-levitation-base.yaml` and flash with ESPHome.

### 2. MQTT topics (Jarvis → globe)

Your Jarvis backend publishes:

| Topic | Values |
|-------|--------|
| `jarvis/globe/state` | `idle`, `listening`, `thinking`, `speaking`, `error` |
| `jarvis/globe/level` | `0.0`–`1.0` (mic / TTS level for pulse) |

### 3. Home Assistant

Import `jarvis/physical/home-assistant/jarvis_globe_light.yaml` and reload automations.

---

## Software companion (optional)

The Three.js orb in `jarvis/` is only for **on-screen** HUD (phone, desktop overlay). Use it **alongside** the physical globe, not instead of it:

- **Physical globe** = desk centerpiece, levitation, room lighting  
- **Screen orb** = chat UI, status, mobile dashboard  

---

## What I can’t do from this repo

- Ship or assemble a physical device  
- Guarantee a specific Amazon SKU in your country  

## Next steps

1. Pick **Arc Reactor** vs **floating globe** vs **DIY wireframe shell**.  
2. If you want smart lighting: say **ESPHome** or **MQTT-only** and your float base diameter — we can tune the LED ring size in the YAML.  
3. Share a photo of the base you bought — wireframe shell and balance notes can be adjusted to that model.
