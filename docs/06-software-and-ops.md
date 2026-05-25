# Software and operations

## OS comparison (expandable homelab NAS)

| Criterion | Unraid | TrueNAS SCALE | OMV + mergerfs |
|-----------|--------|---------------|----------------|
| Expand capacity | **Add one disk** anytime | Vdev-bound (ZFS) | Add disk + merge |
| Mixed drive sizes | **Excellent** | Poor | Good |
| Parity vs mirror | Dual parity plugins | RAIDZ2/3 | No native parity |
| Docker / apps | **Native UI** | K8s + Docker | Manual |
| 24/7 robustness | Good + large community | **Excellent** (ZFS) | Depends on admin |
| ECC support | Yes (hardware) | Yes | Yes |
| Learning curve | Low–medium | Medium–high | Medium |
| License cost | $129+ | Free | Free |

### Verdict for this project

**Primary: Unraid** — best match for phased drive purchases, mixed generations, and Docker-heavy homelab.

**Alternative: TrueNAS SCALE** if you want ZFS snapshots everywhere, Linux VMs as first-class, and are willing to plan vdev layout up front.

**Skip OMV** unless you want maximum DIY control and accept manual parity/merge design.

---

## Unraid configuration baseline

| Setting | Recommendation |
|---------|----------------|
| License | **Plus** (12 devices) or **Pro** if >12 bays |
| File system | XFS on array disks; BTRFS on cache pool |
| Parity | **Dual** parity disks before filling data |
| Docker | `/mnt/user/appdata` on mirrored cache |
| VM | Optional; keep on cache; pin CPU if needed |
| Shares | `media`, `appdata`, `backups`, `isos` |
| Security | Disable FTP; SMB signing; strong admin password |

### Essential plugins / containers

| Component | Purpose |
|-----------|---------|
| **Dynamix** system stats | UI monitoring |
| **Unraid Connect** (optional) | Remote health |
| **Community Apps** | Plugin store |
| **NUT** (Network UPS Tools) | UPS shutdown |
| **Scrutiny** or **HDDashboard** | SMART UI |
| **Tailscale** or **WireGuard** | Remote VPN |
| **Plex** | Media server (primary — see [09-media-centre.md](09-media-centre.md)) |
| **Overseerr** | Plex + *arr* requests |
| **Sonarr / Radarr / Prowlarr / Lidarr** | Library automation |
| **Bazarr** | Subtitles |
| **Recyclarr** | TRaSH profile sync |
| **Tautulli** | Plex monitoring |
| **Gluetun** + download client | VPN for torrents only |

Full media stack, quality phases, and rollout: **[09-media-centre.md](09-media-centre.md)**.

---

## Monitoring and alerting

| Signal | Tool | Alert threshold |
|--------|------|-----------------|
| SMART | Unraid disk settings + Scrutiny | Reallocated > 0 |
| Temps | IPMI + dynamix | HDD > 50 °C |
| Parity | Notifications | Sync error |
| UPS | NUT | On battery > 2 min |
| Capacity | User scripts | Pool > 85% |

**Notification channels:** email (SMTP), Discord webhook, or Pushover.

---

## Update policy

| Component | Policy |
|-----------|--------|
| Unraid OS | Stable branch; monthly check; skip .0 releases 1 week |
| Docker images | Watchtower weekly or manual pin versions |
| Plugins | Update with OS maintenance window |
| Parity / array | Reboot only when required; note rebuild state |

**Maintenance window:** Sunday 03:00 local — parity check, Docker updates, backup verify.

---

## Remote management

| Layer | Access |
|-------|--------|
| Out-of-band | **IPMI** (Supermicro BMC): power, sensors, ISO virtual media |
| In-band | Unraid WebGUI on mgmt VLAN |
| SSH | Key-only; disable root password |
| No public GUI | VPN required from WAN |

### IPMI hardening

- Change default password
- Dedicated VLAN 99
- Disable unused users
- Firmware update from Supermicro support

---

## Security operations

- [ ] SMB: `secure` mode; limit guest
- [ ] Snapshots not a ransomware defense on writable shares — use immutable backup
- [ ] Separate admin account from media read-only users
- [ ] 2FA on Unraid (if plugin) or VPN 2FA at edge
- [ ] Audit open Docker ports (`docker ps`)

---

## Disaster recovery runbook (summary)

1. **Disk fail:** replace → assign → parity rebuild → monitor temps
2. **Cache fail:** replace in pool → balance → restore appdata from backup if needed
3. **Array loss:** provision new hardware → restore from offsite backup
4. **Ransomware:** isolate VLAN → wipe clients → restore from immutable copy

Document RTO/RPO targets in [01-requirements.md](01-requirements.md) when business needs clarify.
