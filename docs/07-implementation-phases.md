# Implementation phases

Phased rollout reduces risk: validate hardware before trusting data migration.

---

## Phase 0 — Planning (current)

| Task | Owner | Done |
|------|-------|------|
| Lock capacity target (50–80 vs 100+ TB) | User | ☐ |
| Choose tier (budget / recommended / premium) | User | ☐ |
| Confirm rack depth and power circuit | User | ☐ |
| Finalize OS (Unraid vs TrueNAS) | User | ☐ |
| Approve BOM | User | ☐ |

**Exit criteria:** Signed-off [02-hardware-bom.md](02-hardware-bom.md) and [08-cost-summary.md](08-cost-summary.md).

---

## Phase 1 — Procure core platform

**Order first (long lead / compatibility critical):**

1. Chassis + rack + PDU
2. Motherboard + CPU + RAM (ECC kit matched)
3. PSU, HBA (pre-flashed IT mode or plan flash)
4. UPS, network switch, 10GbE NIC + DAC
5. Boot USB, cables, thermal paste

**Defer bulk drives** until chassis/HBA POST confirmed.

| Milestone | Verification |
|-----------|--------------|
| Parts received | Inventory vs BOM |
| HBA IT mode | `lspci` shows IT firmware |
| POST | IPMI SEL clear; all DIMMs detected |

---

## Phase 2 — Assembly and bench test

| Step | Detail |
|------|--------|
| 1 | Assemble outside rack; CPU, RAM, HBA, 1× HDD |
| 2 | Cable management dry-fit before full drive load |
| 3 | BIOS: enable ECC, AHCI, fan curves, boot USB |
| 4 | Install Unraid trial; verify all NICs |
| 5 | Stress: `mprime` or `stress-ng` 1 h; watch temps |

**Exit criteria:** 24 h memtest or HCI (optional); idle temps < 40 °C CPU, < 38 °C HDD.

---

## Phase 3 — Drive burn-in (before parity)

Per disk (parallel if spare ports):

| Day | Action |
|-----|--------|
| 1 | SMART short test; record serial |
| 1–3 | `badblocks` or manufacturer diag (destructive) OR Unraid pre-clear |
| 4 | SMART long test; compare to baseline |
| 5 | Add to array as data disk **or** hold as cold spare |

**Do not** enable dual parity until all Phase 3 disks pass.

---

## Phase 4 — Array and cache build

| Order | Action |
|-------|--------|
| 1 | Assign **parity 1**, **parity 2** (largest/newest disks) |
| 2 | Add data disks one generation at a time |
| 3 | Create mirrored NVMe **cache** pool |
| 4 | Run parity sync; expect 1–3 days @ 12×16 TB |
| 5 | Configure shares + Docker on cache |
| 6 | NUT + UPS USB test shutdown |

---

## Phase 5 — Network and security

- [ ] VLANs on switch; NAS bonded or single 10GbE
- [ ] Static IPs; DNS records
- [ ] Firewall rules (see [05-network-and-layout.md](05-network-and-layout.md))
- [ ] VPN for remote; disable port forwards
- [ ] IPMI on mgmt VLAN only

---

## Phase 6 — Services and backup

| Week | Task |
|------|------|
| 1 | Deploy Docker stack (media automation) |
| 2 | Configure local backup job to USB/NAS2 |
| 3 | Configure offsite encrypted backup |
| 4 | **Restore test** — random 10 GB + one Docker volume |

---

## Phase 7 — Data migration

| Source | Method |
|--------|--------|
| Old NAS | rsync over 10GbE; preserve permissions |
| Workstations | Robocopy / rsync weekend window |
| Cloud down | rclone copy; rate limit |

**Tip:** Initial bulk copy with `rsync --ignore-existing`; second pass for delta.

---

## Phase 8 — Production hardening

- [ ] Monthly parity check scheduled
- [ ] Quarterly backup restore drill
- [ ] Document MAC/IP in README decision log
- [ ] Spare disk on shelf labeled
- [ ] Spare USB with Unraid config backup

---

## Timeline (indicative)

| Phase | Duration |
|-------|----------|
| 0 Planning | 1–2 weeks |
| 1 Procure | 2–4 weeks shipping |
| 2–3 Build + burn-in | 1–2 weeks |
| 4–5 Array + network | 1 week |
| 6–7 Services + migration | 2–4 weeks |
| **Total** | **~8–12 weeks** part-time |

---

## Rollback plan

| Stage | Rollback |
|-------|----------|
| Pre-migration | Keep old NAS powered until rsync verify |
| Post-migration | Old NAS read-only 30 days |
| Failed disk during build | RMA; do not add to array |
