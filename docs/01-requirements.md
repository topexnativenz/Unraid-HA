# Requirements and constraints

## Scope

**Homelab / small business** NAS serving:

- Large sequential media libraries (video, audio, photos)
- SMB/NFS shares for workstations
- Docker containers (Plex/Jellyfin, Sonarr/Radarr, Nextcloud, backup agents)
- Optional: VM hosting (1–3 light VMs) on cache pool

Not in scope for v1: multi-node clustering, geo-redundant active-active, or GPU transcoding farm (can add later).

## Capacity targets

### Year 1 (usable after redundancy)

| Metric | Target |
|--------|--------|
| Usable array space | **50–80 TB** |
| Cache (NVMe pool) | **2–4 TB** usable (mirrored) |
| Growth headroom | **4+ empty bays** or upgrade largest drives |

### Example math (recommended build)

- **12× 16 TB** CMR drives, same size
- Unraid **dual parity** → usable ≈ `(12 − 2) × 16 TB` = **160 TB** max if all slots filled
- **Phase 1:** 8 drives (2 parity + 6 data) → **96 TB** usable
- **Phase 2:** add 4 drives → **160 TB** usable

Adjust downward if mixing drive sizes (Unraid usable = sum of data disks capped by smallest).

### 3–5 year growth

| Path | Description |
|------|-------------|
| A — Fill bays | Add 16–20 TB drives into empty bays; parity rebuild per disk |
| B — Replace | Swap smallest drives for larger; schedule parity sync |
| C — Expansion shelf | SAS JBOD + second HBA if >15 spindles needed |

## Performance

| Workload | Target |
|----------|--------|
| Sequential read (array) | 400–800 MB/s aggregate (spinners + 10GbE) |
| Random / metadata | NVMe cache pool |
| Network | **2.5GbE** bonded or single; **10GbE** to core switch if editing 4K/8K |
| Transcode | Optional GPU later; CPU transcoding acceptable for 1–2 streams |

## Availability and durability

| Requirement | Implementation |
|-------------|----------------|
| Uptime | 24/7/365; scheduled monthly maintenance window |
| Disk failure | Dual parity; hot spare optional (empty bay + scripted notify) |
| Power loss | UPS + graceful shutdown (NUT) |
| Memory errors | **ECC RAM** mandatory |
| Data loss | **3-2-1 backup** — array is not backup |

## Constraints

| Item | Constraint |
|------|------------|
| Budget | Cost managed; prefer value at 16 TB CMR tier (~$22–26/TB) |
| Noise | 4U with PWM fans; avoid 15k RPM enterprise unless closet |
| Depth | Rack **≥ 27"** internal for RSV-L4500U class (25" chassis + cables) |
| Power | Single 15A circuit; plan **400–600 W** peak |
| OS skill | Comfortable with Linux CLI; Docker familiarity |

## Non-functional requirements

1. **SMART** monitoring with email/Discord alerts
2. **Remote management** — IPMI/BMC out-of-band
3. **Documented VLAN** separation for management vs storage vs IoT
4. **Expandable** without reformatting entire array (favor Unraid or ZFS expand)

## Open questions (for user refinement)

- [ ] Rack vs tower vs under-desk?
- [ ] Maximum acceptable noise (dBA @ 1 m)?
- [ ] 10GbE to all clients or only editing workstation?
- [ ] Cloud offsite target (B2, Wasabi, iDrive)?
- [ ] Encryption at rest required (Unraid encrypted array)?

## Success criteria

1. Survive **any single disk** failure without data loss
2. Survive **any two disk** failures without data loss (dual parity)
3. Clean shutdown on UPS self-test
4. Restore test from offsite backup quarterly
5. Add one drive without downtime > parity rebuild window
