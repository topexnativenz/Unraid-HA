# Cost summary (USD roll-up)

Approximate **2025–2026 US** pricing. Ranges reflect sales, used vs new, and phase 1 vs full bay count.

**Not included:** labor, electricity, rack space rent, cloud egress, or tax/shipping.

---

## Tier comparison

| Tier | Usable (dual parity) | Drive config | Est. total |
|------|----------------------|--------------|------------|
| **Budget** | ~70–90 TB | 8×14 TB recert + 4U chassis | **$4,500 – $6,500** |
| **Recommended** | ~96 TB → 160 TB | 8–12×16 TB IronWolf Pro | **$8,500 – $11,500** |
| **Premium** | ~160–200 TB | 12×20 TB + 2U SM + rack UPS | **$14,000 – $20,000** |

---

## Recommended tier — line roll-up

| Category | Low | High | Notes |
|----------|-----|------|-------|
| Chassis + rack | $380 | $580 | RSV-L4500U + 12U frame |
| Board + CPU + RAM (64 GB ECC) | $900 | $1,400 | X12STH-F + E-2388G |
| HBA + cables | $120 | $250 | 9300-8i + breakouts |
| PSU + cooling | $150 | $220 | 850 W Gold |
| NVMe cache (2×2 TB) | $280 | $700 | Sale-dependent |
| HDD array (12×16 TB) | $4,200 | $4,800 | IronWolf Pro |
| Network (10G NIC + switch share) | $150 | $400 | NIC + DAC; switch prorated |
| UPS | $220 | $280 | CP1500PFCLCD |
| Misc (USB, labels, spare?) | $50 | $400 | Optional cold spare drive |
| Unraid license | $129 | $129 | Plus |
| **Total** | **~$6,600** | **~$9,200** | Before spare drive |

**With one cold spare 16 TB:** add **$350–400**.

---

## Budget tier — line roll-up

| Category | Est. range |
|----------|------------|
| 4U chassis | $230 |
| Consumer ATX + Ryzen + 32 GB ECC (if available) or used Xeon | $400–700 |
| 8×14 TB Exos recert | $1,600–2,200 |
| Single 9300-8i + cables | $100–180 |
| 1×1 TB NVMe cache (no mirror) | $80–120 |
| 1GbE only | $0 |
| UPS 1000 VA | $150–200 |
| Unraid Starter (6 devices) or Plus | $59–129 |
| **Total** | **$4,500 – $6,500** |

*Risk:* recert drives, single cache, no 10GbE — acceptable for lab, not ideal for production media.

---

## Premium tier — line roll-up

| Category | Est. range |
|----------|------------|
| Supermicro 846 or 836 24-bay (used) | $500–1,200 |
| X12/X13 + Xeon + 128 GB ECC | $1,800–2,800 |
| 12×20 TB IronWolf Pro | $4,800–5,800 |
| Dual 9300-8i or onboard SAS | $200–400 |
| 2×4 TB NVMe mirror | $600–1,200 |
| 10G fiber + enterprise switch ports | $300–600 |
| APC rack UPS SMX1500 | $600–900 |
| Unraid Pro | $129 |
| **Total** | **$14,000 – $20,000+** |

---

## Operating cost (annual, rough)

| Item | Est. / year |
|------|-------------|
| Power (150 W avg × $0.15/kWh) | ~$200 |
| Cloud backup 5 TB @ B2 | ~$30–50 |
| UPS battery replace (3–5 y) | ~$50 amortized |
| Drive RMA pool | $0–400 |

---

## Cost optimization levers

| Lever | Savings | Tradeoff |
|-------|---------|----------|
| 14 TB vs 16 TB | 10–15% | More bays needed sooner |
| Recert Exos | 30–40% on drives | Warranty, noise |
| Start 8 disks not 12 | ~$1,400 | Lower day-1 usable |
| Used 10G NIC | $50 vs $150 | Driver quirks |
| Skip 10G switch port | $0–200 | Wi-Fi bottleneck for 4K |

---

## Procurement priority (cash flow)

1. **Week 1:** chassis, board, CPU, RAM, PSU, HBA, UPS (~$2,000–3,500)
2. **Week 2:** network + NVMe (~$400–900)
3. **Week 3:** first 4 data + 2 parity disks (~$2,100)
4. **Month 2+:** remaining disks as budget allows

---

## Price references (May 2026 research)

| Item | Reference price | Source |
|------|-----------------|--------|
| RSV-L4500U | ~$230 | [Newegg](https://www.newegg.com/rosewill-rsv-l4500u-black/p/N82E16811147328) |
| IronWolf Pro 16 TB | ~$350–400 | [Neowin / Newegg sales](https://www.neowin.net/deals/seagate-ironwolf-pro-20tb-7200-rpm-cmr-nas-hard-disk-is-a-great-deal-after-a-long-time/) |
| IronWolf Pro 20 TB | ~$400–480 | [B&H / Newegg](https://www.bhphotovideo.com/c/product/1760986-REG/seagate_st20000nt001_20tb_ironwolf_pro_7200.html) |
| 9300-8i (used IT) | ~$50–150 | [eBay listings](https://www.ebay.com/itm/166546713042) |
| CP1500PFCLCD | ~$220–240 | [B&H / Newegg](https://www.bhphotovideo.com/c/product/1513053-REG/cyberpower_cp1500pfclcd_pfc_sinewave_ups.html) |
| Samsung 990 Pro 2 TB | ~$130–430 | [Tom's Hardware / Best Buy](https://www.tomshardware.com/pc-components/ssds/samsung-2tb-990-pro-lowest-price-amazon-prime-day-2025-deal) |
| Xeon E-2388G | ~$700 | [Scan UK](https://www.scan.co.uk/products/intel-xeon-e-2388g-s-1200-rocket-lake-8-core-16-thread-32ghz-51ghz-turbo-16mb-20-lane-95w-oem) |

Re-quote all SKUs before purchase; HDD and NVMe volatility is high.
