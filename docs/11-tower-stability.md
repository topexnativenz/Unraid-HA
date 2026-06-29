# Tower stability audit

**Single source of truth** for Unraid tower reliability: drop/crash root causes, health snapshots, and remediation.

**Tower:** `192.168.1.7` (LAN) · `100.79.125.103` (Tailscale) · Unraid 7.1.4 · `Pacific/Auckland`

**Related:** [10-plex-arr-workstream.md](10-plex-arr-workstream.md) (Docker stack, maintenance calendar)

**Last audit:** 2026-06-26 ~09:15 NZST (post-unclean reboot)

---

## Executive summary

**The array is not stopping.** Outages are **full host overload or unclean reboots**, after which Docker/tunnels need time to recover. Tunnels drop because **cloudflared/SWAG** were down while the OS was wedged or rebooting — not because the array stopped.

| Finding | Severity | Evidence |
|---------|----------|----------|
| **Self-inflicted CPU/I/O meltdown** | Critical | Runaway `grep -r /mnt/user`, orphaned `rsync`, daytime SMB bulk copies |
| **Unclean shutdowns** | Critical | `emhttpd: unclean shutdown detected` on every recent boot; XFS journal recovery on disks 1–2 |
| **No swap on 15 GB RAM** | High | OOM risk when dockerd + UniFi + dev containers spike; no swap configured |
| **Array 92% full** | High | `shfs` 40T/44T used — amplifies I/O wait and parity duration |
| **Parity never completed** | High | May 15 check aborted (6 errors); correcting campaign scheduled but interrupted by reboots |
| **SMART reallocated sectors** | Medium | Disk 3 (`sdf`): 16 · Disk 6 (`sdi`): 40 — monitor; plan replacement |
| **Post-reboot Docker fragility** | Medium | Containers `Exited (255)` until `rc.docker restart`; stale port bindings |
| **Broken `/boot/config/go` cron** | Medium (fixed) | Docker-update lines executed as shell at boot (`45: command not found`) |
| **No UPS/NUT** | Medium | No `upsmon`/NUT — unclean shutdowns may be power blips |
| **Restart policy `no`** | Medium (partial fix) | Media/tunnel containers did not auto-start after reboot |

---

## Current health snapshot (2026-06-26)

### Host

| Metric | Value |
|--------|--------|
| Uptime at audit | **~15 min** (reboot **08:58 NZST**) |
| Load | 3–15 (settling post-boot; **65% I/O wait** during container storm) |
| RAM | 15 GiB total, **0 swap** |
| Boot type | **Unclean** (`emhttpd: unclean shutdown detected`) |

### Array

| Metric | Value |
|--------|--------|
| `mdState` | **STARTED** |
| Data disks | 7 slots populated (parity + 6 data); slot 29 empty/disabled |
| All `rdevStatus` | **DISK_OK** (no missing disks at audit) |
| `mdResync` | **0** (idle) |
| `mdResyncAction` | `check P` (parity check scheduled, not active) |
| Capacity | **`/mnt/user` 92%** (40T / 44T) |
| Cache | `/mnt/cache` 48% (224G pool) |
| docker.img | **81%** (32G / 40G loop) |

### Disk SMART (reallocated sectors)

| Slot | Device | Model | Realloc | Temp |
|------|--------|-------|---------|------|
| Parity | `sde` | WD80EFZX 8TB | 0 | 42°C |
| 1 | `sdb` | ST8000VN0002 | 0 | 37°C |
| 2 | `sdg` | ST8000VN0002 | 0 | 45°C |
| **3** | **`sdf`** | ST8000VN0022 | **16** | 43°C |
| 4 | `sdh` | ST8000VN0022 | 0 | 40°C |
| 5 | `sdc` | ST8000NE001 | 0 | 36°C |
| **6** | **`sdi`** | ST8000VN0022 | **40** | 38°C |
| Cache | `sdd` | SSD | n/a | 30°C |

### Services (after remediation this audit)

| Service | Status | Notes |
|---------|--------|--------|
| **Tailscale** | Running | `100.79.125.103`, backend Running |
| **cloudflared** | Up | Was Exited (137) post-reboot — restarted |
| **swag** | Up | Was Exited (255) — restarted; `unless-stopped` set |
| **Plex** | Up (healthy) | HTTP 302 |
| **Sonarr/Radarr/SAB/Prowlarr/lidarr** | Up | Prowlarr/SAB/lidarr had exited — restarted |
| **Overseerr/Tautulli** | Up | |
| **UniFi + mongo** | Up | UniFi Java ~24% CPU post-boot |
| **Voice stack** | Up | livekit, marshal, notified, splash |
| **matariki-property-dev-1** | Up | Next.js dev on `:3000` — **daytime load risk** |

### UPS

**Not configured** — no NUT/upsmon process or `/etc/nut` on tower.

---

## Root causes ranked (with evidence)

### 1. Resource exhaustion → host unresponsive (most common “drop”)

**What users see:** SSH banner timeout, Unraid UI hang, Tailscale/cloud tunnels dead, “array down” (actually **whole OS wedged**).

**Evidence (prior sessions):**
- Load **89–107** on 4-core Xeon with **469 SMB streams on appdata**
- Runaway **`grep -r fix-adoption-loop /mnt/user`** (~7 h full-array scan)
- Orphaned **`rsync`** TV-OLD → TV-NEW consolidation
- Daytime bulk SMB copies (Matariki property uploads to `/mnt/user/appdata/matariki-property`)

**Mechanism:** No swap + heavy page cache + dockerd (~4–5 GiB) + UniFi + concurrent disk I/O → CPU and I/O wait pegged → SSH/nginx/docker unresponsive. Hard reboot → **unclean shutdown**.

**Not:** Array stopping cleanly (`mdState` has remained STARTED across all inspections).

### 2. Unclean shutdown / hard reboot cycle

**Evidence:**
- `emhttpd: unclean shutdown detected` — **2026-06-26 08:58**
- `wtmp` only shows today's boot (logs rotated on reboot)
- Prior: XFS log recovery on disks 1–2 after unclean shutdown (2026-05-23)

**Triggers:** Manual hard reboot when UI/SSH unresponsive; possible **power loss** (UPS not monitored).

### 3. Post-reboot Docker/tunnel gap

**Evidence:**
- Many containers **Exited (255)** or **(137)** after reboot until manual/docker restart
- Prior fix: `/etc/rc.d/rc.docker restart` for stale iptables/docker-proxy
- **cloudflared** and **swag** down = all `*.gillespie.kiwi` tunnels offline even when array is fine

**Impact:** Remote access via Cloudflare/Tailscale fails while LAN may still work briefly.

### 4. Parity debt + array fullness

**Evidence:**
- Parity check **aborted 2026-05-15** with **6 errors**
- Correcting parity cron deployed but **campaign not yet completed** (reboots + window boundaries)
- Array **92% full** increases scan time and I/O contention

### 5. Disk degradation (latent hardware risk)

**Evidence:** SMART reallocated — disk 3 (16), disk 6 (40). No pending sectors at audit. Could cause future sync errors or slow reads under load.

### 6. Configuration bugs (fixed 2026-06-26)

**`/boot/config/go`:** Docker-update cron lines were appended as **shell commands**, causing boot errors:
```
/var/tmp/go: line 15: 45: command not found
```
**Fix:** Merged all maintenance cron into single `crontab` block in `go` (parity, plex, docker-update).

---

## Drop taxonomy

| Symptom | Likely cause | Array stopped? |
|---------|--------------|----------------|
| Tailscale/Cloudflare dead, LAN SSH slow | CPU/I/O meltdown or reboot in progress | No |
| Containers Exited (255) | Post-reboot Docker/proxy state | No |
| UI “array stopped” | Rare; not seen in recent audits — verify `mdState` | Only if emhttp reports stop |
| SSH timeout | Load + I/O wait, not network-only | No |

---

## Fixes applied (2026-06-26 audit)

| Action | Detail |
|--------|--------|
| **Fixed `/boot/config/go`** | Docker-update cron now in `crontab` block; applied live via `bash /boot/config/go` |
| **Started tunnels** | `cloudflared`, `swag` |
| **Started media** | `prowlarr`, `EmbyServer`, `lidarr`, `sabnzbd`, `marshal` |
| **Restart policies** | `docker update --restart=unless-stopped` on cloudflared, swag, Plex, *arr*, voice, unifi, overseerr, tautulli, marshal, livekit |

---

## Recommended fixes

### Immediate (safe anytime)

- [x] Fix `go` cron bug (done 2026-06-26)
- [x] Restart down tunnels/media containers (done 2026-06-26)
- [x] Set `unless-stopped` on critical containers (done 2026-06-26)
- [ ] **Stop daytime SMB bulk copies** to tower (Matariki, TV consolidation)
- [ ] **Stop `matariki-property-dev-1`** when not actively developing (Next.js dev server)
- [ ] Verify cloudflared/SWAG via https://overseerr.gillespie.kiwi from off-LAN

### Maintenance window (00:00–07:00 NZST)

| Priority | Task | ID |
|----------|------|-----|
| P0 | **Complete correcting parity** (3–4 nights) | T1.11 |
| P1 | **Plex DB repair** after parity | T1.8 |
| P1 | **Free ~1.2 TB** stale downloads | T1.6 |
| P2 | **Add swap file on cache** (2–4 GiB) | T1.9 |
| P2 | **Expand or prune docker.img** if >85% sustained | — |
| P3 | **Replace disk 6** (40 realloc) then disk 3 | hardware |

### Infrastructure (schedule separately)

| Item | Recommendation |
|------|----------------|
| **UPS + NUT** | USB UPS → graceful shutdown on power fail; eliminates silent unclean boots |
| **Tunnel watchdog** | Cron every 5 min: if `cloudflared`/`swag` not running → `docker start` (light) |
| **Tailscale** | Already autostarts; ensure **subnets/routes** documented for failover |
| **Monitoring** | UniFi or HA alert on: load >20, `mdResync` active daytime, container down, SMART increment |

### Agent / operator rules

1. **Never** run `grep -r`, `find /mnt/user`, or multi-TB `rsync` outside 00:00–07:00
2. **Never** start parity manually outside window (cron owns T1.11)
3. On “tower down”: try **LAN SSH first** → check `uptime` + `mdState` → distinguish reboot vs tunnel-only

---

## Tunnel resilience checklist

| Layer | Autostart | Watchdog | Notes |
|-------|-----------|----------|-------|
| Tailscale | Yes (OS) | — | Survives reboot if OS clean |
| cloudflared | `unless-stopped` (fixed) | Recommended | Exits on docker/proxy issues |
| swag | `unless-stopped` (fixed) | Recommended | Reverse proxy for all `*.gillespie.kiwi` |
| Plex/*arr* | `unless-stopped` (fixed) | — | Host-network Plex |

| **Tunnel watchdog** | `/boot/config/scripts/tunnel-watchdog.sh` — `*/5 * * * *` in crontab via `go` |

---

## Audit changelog

| Date | Event |
|------|--------|
| 2026-05-23 | CPU meltdown: `grep -r /mnt/user`; hard reboot; unclean shutdown |
| 2026-05-23 | Post-reboot: XFS recovery; parity check cancelled after 40s |
| 2026-05-26 | Docker cleanup; Overseerr/Tautulli/splash fixed |
| 2026-06-26 | **Unclean reboot 08:58**; tunnels/media down; `go` cron bug fixed; services restored |

---

## Next audit triggers

Re-run this checklist after:
- Any unclean shutdown or hard reboot
- SMART realloc increment on disk 3 or 6
- Parity campaign completion (T1.11)
- Adding swap or UPS

Quick command bundle (read-only):

```bash
ssh -i /Users/topexnative/.ssh/id_ed25519_unraid root@192.168.1.7 '
  date; uptime; free -h; swapon --show
  grep mdState /var/local/emhttp/var.ini
  df -h /mnt/user /mnt/cache /var/lib/docker
  docker ps -a --format "{{.Names}}|{{.Status}}" | grep -iE "Exited|Restart"
  tailscale status | head -3
'
```
