# Redundancy and array design

## Philosophy

The array protects against **hardware failure** (disk, PSU, NIC). It does **not** protect against ransomware, fire, theft, or admin error. **Backups** (3-2-1) are mandatory.

```
3 copies of data
2 different media types
1 offsite copy
```

---

## Unraid array model (recommended)

| Layer | Technology | Redundancy |
|-------|------------|------------|
| Data disks | XFS per disk | None per-disk; spread across spindles |
| Parity 1 | Dedicated parity disk | Survives **1** disk failure |
| Parity 2 | Second parity disk | Survives **2** simultaneous failures |
| Cache pool | BTRFS or ZFS mirror (2+ NVMe) | Survives 1 NVMe failure |
| Boot | USB flash | Keep backup flash |

### Usable capacity (same-size disks)

```
usable_TB ≈ (N_data_disks) × size_TB
where N_data_disks = total_disks − 2   (dual parity)
```

Example: 12×16 TB, all parity slots filled → **10 × 16 = 160 TB** usable.

### Mixed-size disks

Unraid allows expanding with larger drives; usable space grows to the sum of data disks, each capped by its size. **Plan one drive size per generation** to avoid stranded capacity.

---

## Comparison: Unraid vs ZFS (TrueNAS)

| Aspect | Unraid dual parity | ZFS RAIDZ2 |
|--------|-------------------|------------|
| Expand | Add **one** disk at a time | Add vdev or replace all in vdev |
| Mixed sizes | Native | Poor fit |
| Parity rebuild | Single-disk read/modify/write | Full stripe rebuild |
| RAM | 8–64 GB ECC typical | 32–128 GB+ for dedup (avoid dedup) |
| Snapshots | Limited on array; better on pool | Native everywhere |
| Docker | Excellent | Good (K8s tilt) |

**Recommendation:** Unraid for this project’s expand-by-disk requirement. TrueNAS SCALE if team prefers ZFS snapshots and Linux-native VMs over Unraid’s Docker UX.

---

## Cache pool strategy

| Pool name | Devices | Purpose |
|-----------|---------|---------|
| `cache` | 2× 2 TB NVMe **mirror** | appdata, Docker, VM disks, downloads |
| `array` | 8–12× HDD | bulk media, archives, cold data |

### Mover policy

- **Prefer cache:** `appdata`, `system`, active Docker volumes
- **Array only:** completed media libraries, backups landing zone
- **Turbo write:** enable during bulk ingest; disable for 24/7 stability

### Do not put on cache without mirror

Unraid allows unprotected cache — **avoid** for anything you cannot rebuild.

---

## Hot spare

| Option | Pros | Cons |
|--------|------|------|
| Empty bay + spare disk on shelf | No idle spin; manual swap | Slower recovery |
| Dedicated hot spare disk | Faster rebuild trigger | Powered, unused TB |
| Unraid parity valid + notify | No extra disk | Requires purchasing ASAP |

**Recommended:** keep **one sealed spare** matching array model; script SMART daily + email on reallocated sectors.

---

## PSU and network redundancy

| Component | Approach |
|-----------|----------|
| PSU | Single **850 W** quality unit (B/R); dual PSU only on enterprise chassis |
| NIC | Dual-port 10GbE; LACP to switch if switch supports it; else failover |
| Switch | Core switch with redundant uplink to router |
| Internet | Out of scope; NAS survives ISP outage locally |

---

## Failure modes and response

| Event | Impact | Response |
|-------|--------|----------|
| 1 disk failure | Array degraded; no data loss | Replace disk; parity rebuild 24–72 h @ 16 TB |
| 2 disk failure (dual parity) | Degraded; no loss if different disks | Replace both; rebuild |
| 3+ disk failure | **Data loss** on array | Restore from backup |
| Cache pool 1 disk (mirror) | None if mirror intact | Replace NVMe |
| Both cache disks | Loss of un-moved cache files | Restore appdata from backup |
| PSU failure | Hard down | Spare PSU or RMA |
| UPS exhausted | Unclean shutdown risk | NUT shutdown at 20% battery |
| Ransomware | Encrypted shares | Immutable/offsite backup only fix |
| Bit rot | Silent corruption | Parity check monthly; scrub cache BTRFS |

### Rebuild stress

Parity rebuild reads **all** remaining disks — second failure during rebuild is elevated risk. **Do not** run heavy IO during rebuild; consider **parity check** before failure season.

---

## Backup strategy (3-2-1)

| Copy | Location | Tool examples |
|------|----------|---------------|
| 1 | On array | Live data |
| 2 | Local USB HDD or second NAS | rsync / rclone / UrBackup |
| 3 | Cloud (B2, Wasabi) or friend’s NAS | restic / rclone encrypted |

**Versioning:** enable snapshots on backup target, not only live share.

**Test restores:** quarterly random file + annual full VM restore.

---

## Monitoring checklist

- [ ] SMART long test on new disks before array join
- [ ] Unraid notifications → email/Discord/Telegram
- [ ] Parity check scheduled (monthly or quarterly)
- [ ] UPS NUT: `SHUTDOWN` at `BATTERYLEVEL 20`
- [ ] Temperature alerts > 45 °C HDD
