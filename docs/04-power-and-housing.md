# Power and housing

## Form factor decision

| Option | Best for | Pros | Cons |
|--------|----------|------|------|
| **4U tower/rack** (RSV-L4500U) | Homelab, 12–15 disks | Cheap bays, simple SATA | Large footprint, fan noise |
| **2U rack** (Supermicro 846) | Dense rack, IPMI | 24 bays, BMC | Noise, depth, weight |
| **Tower** (Fractal / Silverstone) | Quiet office | Low noise | ≤8 disks typical |

**Default recommendation:** **4U rackmount** on casters in closet, or **4U short-depth** if rack is shallow.

---

## Physical dimensions (RSV-L4500U reference)

| Spec | Value |
|------|-------|
| Form factor | 4U rackmount |
| Drive bays | 15× internal 3.5" |
| Chassis (W×H×D) | 16.8" × 7" × 25" |
| With handles | 19.1" × 7" × 27.2" |
| Weight (empty) | ~31 lb |
| Max PSU length | 220 mm |
| Max CPU cooler height | 152 mm (no GPU) |

Ensure rack **depth ≥ 27"** and **80 lb+ static load** rating.

---

## Cooling and airflow

```
[ Front intake: 6×120mm ] → [ HDD cage ] → [ CPU/HBA ] → [ Rear exhaust: 2×80mm ]
```

| Practice | Detail |
|----------|--------|
| Fan curve | IPMI or BIOS: ramp 40% @ 35 °C, 80% @ 50 °C |
| Cable management | Route SATA along side; avoid blocking middle fan row |
| Dust | Front filter mesh; quarterly clean |
| Ambient | Target closet **< 30 °C** year-round |

**Noise expectation:** 35–45 dBA @ 1 m under load with PWM fans; enterprise 15k drives add whine.

---

## Power budget

### Component estimates (12-disk spin-up)

| Component | Idle W | Active W | Notes |
|-----------|--------|----------|-------|
| 12× HDD (16 TB class) | 60–70 | 90–120 | ~5–8 W idle, ~7–10 W active each |
| CPU (E-2388G) | 25–35 | 65–95 | Transcode higher |
| Motherboard + RAM | 15–25 | 20–30 | ECC |
| HBA + NVMe | 10–15 | 25–40 | |
| Fans | 15–25 | 25–40 | |
| **Total** | **125–170** | **250–400** | |
| **Spin-up surge** | — | **500–650** | <10 s; PSU headroom critical |

### PSU sizing

```
PSU_W ≥ (peak_load_W × 1.3) + margin
→ 650 W minimum; **850 W recommended** for 12–15 disks + 10GbE
```

Use **80+ Gold**; single-rail preferred for HDD inrush.

---

## UPS sizing

| UPS model class | VA / W | Runtime @ 200 W | Fit |
|-----------------|--------|-----------------|-----|
| CP1500PFCLCD | 1500 / 1000 | ~10–15 min | **Recommended** homelab |
| CP1000PFCLCD | 1000 / 700 | ~5–8 min | Tight; OK for ≤8 disks |
| SMX1500RM2U | 1500 rack | ~10 min | Premium rack |

**Sizing rule:** UPS output watts ≥ peak NAS draw; aim **≥10 min** at average load for graceful shutdown.

### NUT shutdown chain

```
UPS (USB) → NUT on Unraid → NOTIFY → shutdown -h now @ LOWBATT
```

Also protect **switch + router** on separate UPS outlet group if budget allows.

---

## PDU and cabling

| Item | Guidance |
|------|----------|
| PDU | 1U metered; **C13** outlets for server, switch, UPS loop |
| Cables | Separate **data** (left) vs **power** (right) bundle |
| Color | Red = IPMI/mgmt; blue = 10GbE storage; gray = 1GbE |
| Label | Hostname + port on each end |

---

## Rack layout (example 15U stack)

```
┌─────────────────────────┐  U15  Blank / patch panel
├─────────────────────────┤  U14  1U brush panel
├─────────────────────────┤  U13  Switch (24-port 2.5G)
├─────────────────────────┤  U12  Shelf: router / AP
├─────────────────────────┤  U11  Blank (cable slack)
├─────────────────────────┤  U10–U7  NAS 4U (RSV-L4500U)
├─────────────────────────┤  U6   Blank (airflow)
├─────────────────────────┤  U5   UPS shelf (tower UPS)
├─────────────────────────┤  U4–U1  Cable management / PDU
└─────────────────────────┘
```

---

## Environmental

| Risk | Mitigation |
|------|------------|
| Heat soak | Door vent or exhaust fan in closet |
| Humidity | Avoid basement flooding; elevate shelf |
| Vibration | Rack feet level; RV sensors on IronWolf help |
| Fire | Smoke detector; no propane heater in same room |
