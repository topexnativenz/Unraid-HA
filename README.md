# Unraid / NAS Array Design

Planning repository for a **homelab / small-business** storage array: hardware, redundancy, power, network, software, and rollout. This is **infrastructure planning only** — no application code yet.

## Goals

| Goal | Target (default assumptions) |
|------|------------------------------|
| Usable capacity (year 1) | **50–80 TB** |
| Growth path (3–5 years) | **100–150 TB** without forklift |
| Availability | 24/7/365; survive single-disk and most double-disk scenarios |
| Performance | NVMe cache pool; **2.5GbE** minimum, **10GbE** optional on backbone |
| Cost | Managed but not the primary constraint — favor NAS-grade parts |

## Recommended direction (executive)

1. **Chassis:** 4U rackmount with **12–15** internal 3.5" bays (e.g. Rosewill RSV-L4500U) or 2U Supermicro if noise/depth matter less.
2. **Array:** **12× 16 TB** CMR NAS drives (IronWolf Pro / WD Red Pro sweet spot); start with **8 data + 2 parity** (dual parity), expand into empty bays.
3. **Cache:** **2× 2 TB NVMe** mirrored pool (Samsung 990 Pro class) for appdata / VM / hot datasets.
4. **Parity:** Unraid **dual parity** (XFS array + parity plugins); **3-2-1** backups to separate system/cloud.
5. **UPS:** **1500 VA / 1000 W** sine-wave PFC (CyberPower CP1500PFCLCD class) + NUT graceful shutdown.
6. **OS:** **Unraid** for mixed-capacity expansion and Docker ecosystem; TrueNAS SCALE if ZFS-native snapshots and Linux VMs are paramount.

## Document map

| Doc | Contents |
|-----|----------|
| [docs/01-requirements.md](docs/01-requirements.md) | Goals, constraints, capacity math |
| [docs/02-hardware-bom.md](docs/02-hardware-bom.md) | Itemized BOM (budget / recommended / premium) |
| [docs/03-redundancy-and-array.md](docs/03-redundancy-and-array.md) | Parity, cache, failure modes, backups |
| [docs/04-power-and-housing.md](docs/04-power-and-housing.md) | Rack/tower, cooling, UPS, wattage |
| [docs/05-network-and-layout.md](docs/05-network-and-layout.md) | Topology, VLANs, mermaid diagrams |
| [docs/06-software-and-ops.md](docs/06-software-and-ops.md) | OS comparison, monitoring, updates |
| [docs/07-implementation-phases.md](docs/07-implementation-phases.md) | Procure → burn-in → migrate |
| [docs/08-cost-summary.md](docs/08-cost-summary.md) | Roll-up USD ranges |
| [docs/09-media-automation.md](docs/09-media-automation.md) | Sonarr/Radarr/Prowlarr/Plex stack (live tower) |
| [docs/09-media-centre.md](docs/09-media-centre.md) | Plex, *arr*, Sonos, Apple TV, rollout |
| [docs/10-plex-arr-workstream.md](docs/10-plex-arr-workstream.md) | Tower audit, unified tasks, Plex & *arr session |
| [docs/11-ios-media-ops.md](docs/11-ios-media-ops.md) | iOS Helmarr, Tautulli/Overseerr, push notifications |
| [docs/12-ceiling-speakers-per-room.md](docs/12-ceiling-speakers-per-room.md) | Ceiling speakers ↔ TV / Apple TV / Sonos Amp per room |

## Assumptions (refine as needed)

- Region: **USD** pricing (US retailers / eBay); adjust ~10–20% for EU/UK VAT.
- Workload: media + file shares + Docker (Plex, *arr*, backups); not primary database OLTP.
- Media centre: **Plex** (lifetime Pass), **Sonos**, all-**Apple** clients — see [docs/09-media-centre.md](docs/09-media-centre.md).
- No colocation; on-prem closet or shallow rack in office/home.
- Remote management via **IPMI** (Supermicro BMC) or Intel AMT where available.

## Decision log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-23 | Default project name `unraid-array-design` | Homelab NAS planning scope |
| 2026-05-23 | Target **~80 TB usable** @ dual parity on 12×16 TB | Balance $/TB and bay count |
| 2026-05-23 | **Unraid** as primary OS recommendation | Best fit for expand-by-single-disk and Docker |
| 2026-05-23 | **Dual parity + mirrored NVMe cache** | Survive 2 disk losses in array; protect metadata/hot IO |
| 2026-05-23 | **Plex-only** media server; no Jellyfin | Lifetime Pass; Apple TV household |
| 2026-05-23 | *arr* quality **phase 1 = fast WEB-1080p** | New releases before 4K/remux; revisit post-hardware |
| 2026-05-23 | **Sonos** + Apple Music / Spotify; Plexamp later | Whole-home audio unchanged for now |
| 2026-07-19 | **Sonos Amp + ceiling speakers** per TV room | Passive in-ceiling driven from TV eARC/ARC; see [docs/12-ceiling-speakers-per-room.md](docs/12-ceiling-speakers-per-room.md) |
| 2026-05-23 | **10-plex-arr-workstream.md** = canonical Plex/*arr tasks | Merged media-centre + tower audit chats |

## Active Cursor sessions

| Session | Scope | Canonical doc |
|---------|--------|----------------|
| **Plex & *arr's** | Tower changes, audit execution, Sonarr/Radarr/Plex | [docs/10-plex-arr-workstream.md](docs/10-plex-arr-workstream.md) |
| NAS array design | Hardware, network, migration | [docs/01-requirements.md](docs/01-requirements.md) … [08-cost-summary.md](docs/08-cost-summary.md) |

## Pricing note

BOM figures use **approximate 2025–2026 US street prices** from Newegg, B&H, Amazon, and eBay (used enterprise). Sale events (Prime Day, Black Friday) can swing NVMe and HDD pricing ±30%. See [docs/08-cost-summary.md](docs/08-cost-summary.md).

## Next steps

1. Confirm rack depth (27" vs 29"+) and noise tolerance.
2. Lock drive size (14 TB vs 16 TB vs 20 TB) based on bay count and budget.
3. Order HBA + cables first; burn-in drives before parity build.
4. Update decision log when OS or chassis tier is finalized.
