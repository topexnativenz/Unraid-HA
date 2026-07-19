# Ceiling speakers ↔ room TVs

How to drive **passive in-ceiling speakers** from each room’s **TV + Apple TV**, while staying aligned with the household stack in [09-media-centre.md](09-media-centre.md): **Plex → Apple TV 4K → TV**, and **Sonos** for whole-home audio.

**Last updated:** 2026-07-19

---

## Executive recommendation

| Decision | Choice |
|----------|--------|
| Per-room TV audio amp | **Sonos Amp** (one per room with a stereo ceiling pair) |
| Signal path for TV / Plex | **Apple TV → HDMI → TV → HDMI eARC/ARC → Sonos Amp → speaker wire → ceiling pair** |
| Music / multi-room | Same Amp zones in the **Sonos app** (group with existing Sonos) |
| Passive speaker wire | **16 AWG** CL2/CL3 in-wall (or **14 AWG** for runs &gt; ~25 m) |
| Dedicated home theatre | Separate AVR later — see [Future HT](#dedicated-home-theatre-later); do not force AVR into every bedroom |

**Why not wire speakers straight into the TV?** Almost all TVs have **line-level** optical / HDMI ARC outputs, not powered speaker terminals. Ceiling speakers need an **amplifier**. The Amp is that amp — and it keeps music on the Sonos ecosystem you already use.

---

## Per-room signal path

```mermaid
flowchart LR
  ATV[Apple TV 4K]
  TV[TV]
  AMP[Sonos Amp]
  SP["Ceiling L / R"]

  ATV -->|HDMI| TV
  TV -->|HDMI eARC or ARC| AMP
  AMP -->|Speaker wire| SP
```

| Hop | Detail |
|-----|--------|
| Apple TV → TV | HDMI (prefer HDMI that supports ARC on the TV side, usually labelled **ARC / eARC**) |
| TV → Amp | **HDMI eARC** preferred; **HDMI ARC** OK; optical TOSLINK only if the TV has no usable ARC |
| Amp → speakers | Binding posts → **+ / −** for Left and Right; observe polarity |
| Network | Amp on **VLAN 10** (client LAN) with other Sonos + Apple TVs ([05-network-and-layout.md](05-network-and-layout.md)) |

### TV settings (every room)

1. External speakers / audio out = **HDMI ARC** (or **eARC**).
2. Disable TV speakers (or set to “audio system”) so sound only comes from the ceiling pair.
3. Turn **off** night mode / auto volume if dialogue sounds pumped or dull.
4. On Apple TV: Audio → leave default; Atmos tracks will usually downmix to stereo PCM into the Amp — fine for 2.0 ceiling installs.

### Sonos app

- Name each Amp by room (match Alexa / Home room names to avoid voice confusion).
- Use **TV** source on that room’s Amp for movies; use Music / grouping for Spotify / Apple Music as today.
- Trueplay (if available for Amp + room) after furniture is in place.

---

## Speaker wiring (physical)

### Cable

| Item | Spec |
|------|------|
| Type | Oxygen-free copper speaker cable, **in-wall rated** (CL2/CL3 or local NZ equivalent) |
| Gauge | **16 AWG** typical stereo run; **14 AWG** if long attic runs or 4Ω speakers |
| Topology | **Home-run** from Amp location to each speaker (no daisy-chain of stereo pairs) |
| Polarity | Mark / stripe the **+** conductor end-to-end; reverse polarity = weak bass and odd imaging |

### Amp placement

Prefer the Amp **near the TV** (AV niche, media cabinet, or wall plate behind TV):

- Short HDMI ARC cable (≤ 2 m ideal).
- Power outlet for Amp.
- Cat6 to switch or AP backhaul if Wi‑Fi is weak (wired Sonos is more reliable — see Alexa/Sonos notes in media centre doc).

If the Amp must live in a closet, use a longer HDMI ARC run only with a quality certified cable, or use the TV’s **optical** out as fallback (loses eARC features).

### Ceiling speakers

| Check | Guidance |
|-------|----------|
| Impedance | Match Amp rating (Sonos Amp: typically **8Ω** stereo pair; confirm current Amp gen spec before buying 4Ω models) |
| Sensitivity | Higher dB/W is better for dialogue at modest volume |
| Placement | L/R roughly equidistant from seating; avoid putting both over the same side of the couch |
| Backboxes / fire hoods | Use where code / insulation requires; improves bass consistency |

### Rough install sequence (one room)

1. Pull speaker cable while ceilings/attic are open; leave service loops at speaker cutouts and at Amp location.
2. Mount speakers; terminate with banana plugs or spades if Amp posts allow.
3. Mount Amp; connect speakers, power, Ethernet (or Wi‑Fi), HDMI ARC to TV.
4. Add Amp in Sonos app; set room name; enable TV HDMI source.
5. Play a stereo test track + a Plex movie dialogue scene; balance volume via TV vs Sonos app once, then leave TV volume as primary remote if using CEC/ARC volume.

---

## Room rollout pattern

Treat every “TV room” the same; scale by buying Amps as rooms are finished.

| Room type | Pattern |
|-----------|---------|
| Lounge / family | Stereo ceiling pair + Sonos Amp; optional later surrounds / sub (Sonos Sub or Amp line-out) |
| Bedroom / office | Same 2.0 pattern; keep volume limits reasonable for thin ceilings |
| Future HT | Dedicated AVR + Atmos speakers — **not** a second Sonos Amp pretending to be a cinema |

**Do not** share one Amp across multiple rooms’ TVs. ARC is one TV at a time; multi-room TV audio needs **one Amp (or equivalent) per TV**.

---

## Alternatives (when not using Sonos Amp)

Use these only if you deliberately leave the Sonos path for a room.

| Approach | When it makes sense | Drawbacks |
|----------|---------------------|-----------|
| **Stereo power amp + TV optical/ARC extractor** | Cheap 2.0, no Sonos music needed in that room | No Sonos grouping; another remote / app |
| **AV receiver per room** | True surround in that room | Cost, heat, complexity; overkill for bedrooms |
| **Active / powered ceiling speakers** | Amp built into speakers; TV optical or line-in | Harder multi-room music; still need a network path if “smart” |
| **Sonos Port + external amp** | You already own a good amp | Extra box; Port has no HDMI ARC (use optical / analog) |

For this household, **Sonos Amp remains the default** so TV audio and music stay one ecosystem.

---

## Network and control checklist

Align with [05-network-and-layout.md](05-network-and-layout.md) and [09-media-centre.md](09-media-centre.md).

- [ ] Each Amp on **VLAN 10** with Apple TVs and existing Sonos
- [ ] Prefer **wired Ethernet** to Amp where a drop exists
- [ ] mDNS / Sonos discovery not blocked between Amps and controllers (phones, Alexa)
- [ ] Room names consistent across Sonos, Apple Home (if used), and Alexa
- [ ] After adding Amps, re-test **Plex on Apple TV** dialogue levels and **Spotify / Apple Music** grouping

---

## Dedicated home theatre (later)

When the HT room is built ([09-media-centre.md — Future HT](09-media-centre.md#future-home-theatre-room)):

- Use an **AVR** with eARC, Atmos speaker layout, and wired Ethernet to the streamer.
- Keep bedroom / living ceiling installs on **Sonos Amp** — do not rip them out for the HT design.
- Optionally link HT into Sonos (Sonos surrounds / “Sonos for home theatre” products, or line-in) as a separate decision.

---

## BOM sketch (per TV room)

| Item | Qty | Notes |
|------|-----|-------|
| In-ceiling speakers (stereo pair) | 1 pair | 8Ω class; paintable grille |
| Sonos Amp | 1 | HDMI ARC/eARC capable gen |
| Speaker cable 16 AWG in-wall | As needed | Home-run L and R |
| HDMI cable (ARC) | 1 | Short; eARC-capable |
| Ethernet drop (optional) | 1 | Cat6 to Amp |

Update [08-cost-summary.md](08-cost-summary.md) when room count and speaker model are locked.

---

## Success criteria

1. Each finished TV room plays **Plex / Apple TV** audio from the ceiling pair with no TV-speaker fallback.
2. Same room’s Amp appears in **Sonos** and can group with existing speakers for music.
3. Polarity and levels verified with a mono dialogue clip (voice centered, not thin).
4. No extra AVRs in bedrooms; HT deferred to its own design.

---

## Decision log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-19 | **Sonos Amp per TV room** drives passive ceiling speakers | Matches existing Sonos + Apple TV stack; TVs are not power amps |
| 2026-07-19 | **HDMI eARC/ARC** TV → Amp as primary path | Best lip-sync and volume control vs optical-only |
| 2026-07-19 | One Amp per TV; no shared Amp across rooms | ARC is single-source; multi-room TV needs per-room amps |

---

## Related documents

| Doc | Link |
|-----|------|
| Media centre strategy | [09-media-centre.md](09-media-centre.md) |
| Network / VLANs | [05-network-and-layout.md](05-network-and-layout.md) |
| Plex / *arr* workstream | [10-plex-arr-workstream.md](10-plex-arr-workstream.md) |
| Cost roll-up | [08-cost-summary.md](08-cost-summary.md) |
