# Hardware bill of materials (BOM)

**Region:** USD, US retailers (Newegg, B&H, Amazon) + eBay used enterprise.  
**Pricing era:** approximate **2025–2026** street; verify before purchase.

Legend: **B** = budget tier · **R** = recommended · **P** = premium

---

## Chassis and rack

| Qty | Item | Tier | Est. USD | Notes |
|-----|------|------|----------|-------|
| 1 | Rosewill RSV-L4500U 4U (15×3.5") | B/R | $230 | [Newegg ~$230](https://www.newegg.com/rosewill-rsv-l4500u-black/p/N82E16811147328); 6×120mm + 2×80mm fans |
| 1 | Rosewill RSV-L4500U-SK (high-airflow fans) | R | $300 | Quieter PWM fans pre-installed |
| 1 | Supermicro CSE-846 / 836 2U-3U (used) | P | $400–900 | 24-bay SAS backplane; louder; IPMI chassis options |
| 1 | 12–15U open frame rack or StarTech 4-post | R | $150–350 | Depth ≥27"; includes casters |
| 1 | Rack shelf (UPS / switch) | R | $40–80 | |

---

## Motherboard, CPU, RAM

| Qty | Item | Tier | Est. USD | Notes |
|-----|------|------|----------|-------|
| 1 | Supermicro X12STH-F (C256, IPMI, 4×ECC DIMM) | R | $350–650 | [Refurb ~$613](https://www.gotodirect.com/supermicro-x12sth-f-lga1200-c256-chipset-m-atx-motherboard); M.2 for boot |
| 1 | Supermicro X12SCA-F (workstation, no IPMI) | B | $250–400 | If BMC not required |
| 1 | Intel Xeon E-2336 (6C) | B | $200–280 | Lower cost; still ECC |
| 1 | Intel Xeon E-2388G (8C) | R/P | $500–700 | [Scan ~£690 / ~$700](https://www.scan.co.uk/products/intel-xeon-e-2388g-s-1200-rocket-lake-8-core-16-thread-32ghz-51ghz-turbo-16mb-20-lane-95w-oem); Plex/transcode headroom |
| 2 | 32 GB DDR4 ECC UDIMM 3200 (64 GB total) | R | $180–280 | Samsung/SK hynix; 128 GB for VMs |
| 1 | CPU cooler (Arctic Freezer 34 / Noctua NH-U9S) | R | $40–70 | LGA-1200; watch 4U height limit (~152 mm) |
| 1 | USB flash 32 GB (Unraid boot) | R | $15 | SanDisk Ultra Fit |

---

## Storage — array (3.5" CMR)

| Qty | Item | Tier | Est. USD (each) | Notes |
|-----|------|------|-----------------|-------|
| 8–12 | Seagate IronWolf Pro **16 TB** | R | $350–400 | ~$22–25/TB; [16TB ~$370 sale](https://www.neowin.net/deals/seagate-ironwolf-pro-20tb-7200-rpm-cmr-nas-hard-disk-is-a-great-deal-after-a-long-time/) |
| 12 | Seagate IronWolf Pro **20 TB** | P | $400–480 | ~$22–24/TB; max density per bay |
| 12 | WD Red Pro 16 TB | R | $360–420 | Alternative CMR NAS |
| 12 | Recert Seagate Exos 14–16 TB | B | $180–280 | eBay; shorter warranty; burn-in mandatory |

**Phase 1 array cost (8×16 TB):** ~$2,800–3,200  
**Full 12×16 TB:** ~$4,200–4,800  

---

## Storage — cache / boot

| Qty | Item | Tier | Est. USD | Notes |
|-----|------|------|----------|-------|
| 2 | Samsung 990 Pro 2 TB NVMe (mirror pool) | R | $260–430 ea | [$133–430 depending on sale](https://www.tomshardware.com/pc-components/ssds/samsung-2tb-990-pro-lowest-price-amazon-prime-day-2025-deal); 1200 TBW |
| 2 | Crucial T500 2 TB | B | $140–200 ea | Value NVMe cache |
| 1 | Optional SATA SSD 500 GB | B | $50 | Unraid boot backup |

---

## HBA, cables, backplane

| Qty | Item | Tier | Est. USD | Notes |
|-----|------|------|----------|-------|
| 1–2 | LSI/Broadcom 9300-8i (IT mode) | R | $50–150 | [eBay used ~$115](https://www.ebay.com/itm/166546713042); flash IT firmware |
| 2 | SFF-8643 → 4×SATA forward breakout | R | $25–40 ea | Match port count to drives |
| 1 | SAS2/3 expander (if 846 chassis) | P | $80–150 | Only for backplane chassis |
| 15 | SATA data cables 50–75 cm | R | $30 pack | Right-angle for 4U |
| 2 | SAS/SATA power splitters (if PSU limited) | R | $20 | Quality Molex/SATA only |

---

## Power supply

| Qty | Item | Tier | Est. USD | Notes |
|-----|------|------|----------|-------|
| 1 | Seasonic Focus GX-850 (80+ Gold) | R | $120–150 | Single PSU; headroom for spin-up |
| 1 | Corsair RM850x | R | $110–140 | Alternative |
| 1 | Dual redundant PSU module | P | +$200 | Supermicro chassis only |

---

## Network

| Qty | Item | Tier | Est. USD | Notes |
|-----|------|------|----------|-------|
| 1 | Intel X550-T2 10GbE RJ45 | R | $80–150 | Used; dual port |
| 1 | Mellanox ConnectX-3 Pro 10GbE SFP+ | B | $35–60 | eBay; needs DAC/fiber |
| 1 | Ubiquiti USW-Pro-24-PoE or Pro Max 16 | R | $400–700 | 2.5G + 10G SFP+ uplink |
| 2 | 10GbE DAC 0.5 m (DAC) | R | $20–35 | Server ↔ switch |

Onboard 1GbE (IPMI separate): keep management on dedicated VLAN.

---

## UPS, PDU, power

| Qty | Item | Tier | Est. USD | Notes |
|-----|------|------|----------|-------|
| 1 | CyberPower CP1500PFCLCD (1500VA/1000W) | R | $220–240 | [B&H ~$220](https://www.bhphotovideo.com/c/product/1513053-REG/cyberpower_cp1500pfclcd_pfc_sinewave_ups.html); sine-wave PFC |
| 1 | APC SMX1500RM2U (rackmount) | P | $600–900 | 2U rack; network card optional |
| 1 | Basic 1U metered PDU | R | $40–80 | Per-outlet metering optional |
| 1 | Surge protector (network path) | R | $30 | Modem/AP |

---

## Miscellaneous

| Qty | Item | Est. USD | Notes |
|-----|------|----------|-------|
| 1 | Kill-a-watt or PDU metering | $25 | Validate idle/peak |
| 1 | Label printer / cable labels | $20 | Asset tags |
| 1 | Spare drive (cold stand-by) | $350+ | Same model as array |
| — | Unraid Plus license | $129 | [unraid.net](https://unraid.net) |

---

## Tier summaries (complete system, ex-labor)

| Tier | Drives | Usable (dual parity) | Est. total USD |
|------|--------|----------------------|----------------|
| **Budget** | 8×14 TB Exos recert | ~84 TB | $4,500–6,500 |
| **Recommended** | 12×16 TB IronWolf Pro | ~160 TB (or 96 TB @ 8 disks) | $8,500–11,500 |
| **Premium** | 12×20 TB + 2U SM + rack UPS | ~200 TB | $14,000–20,000+ |

See [08-cost-summary.md](08-cost-summary.md) for roll-up and optional line items.
