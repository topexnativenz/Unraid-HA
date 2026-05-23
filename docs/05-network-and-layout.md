# Network and infrastructure layout

## Design principles

1. **Management** (IPMI, switch admin) separated from **storage traffic**
2. **Clients** reach NAS via dedicated storage VLAN or L2 same-subnet for homelab
3. **Backups** can use isolated VLAN with firewall rules to NAS only
4. **No direct internet exposure** of SMB/NFS — VPN or reverse proxy for remote

---

## High-level topology (mermaid)

```mermaid
flowchart TB
    subgraph Internet
        ISP[ISP Modem / ONT]
    end

    subgraph Edge["Edge / Firewall"]
        FW[Router / OPNsense]
    end

    subgraph Core["Core L2/L3"]
        SW[Managed Switch\n2.5G + 10G SFP+]
    end

    subgraph Storage["Storage VLAN 20"]
        NAS[Unraid NAS\n10GbE + 1GbE mgmt]
        IPMI[IPMI BMC\nVLAN 99]
    end

    subgraph Clients["User VLAN 10"]
        WS[Workstations]
        WIFI[Wi-Fi AP]
        HTPC[Media Players]
    end

    subgraph Backup["Backup VLAN 30"]
        BKP[Backup target / cloud agent]
    end

  ISP --> FW
  FW --> SW
  SW --> NAS
  SW --> WS
  SW --> WIFI
  SW --> HTPC
  SW --> BKP
  IPMI -.-> NAS
  FW -. VPN .-> WS
```

---

## Physical layout (mermaid)

```mermaid
flowchart LR
    subgraph Rack["15U Closet Rack"]
        direction TB
        SW2[Switch U13]
        NAS2[NAS 4U U7-10]
        UPS2[UPS U5]
    end

    subgraph Office
        PC[Editing PC\n10GbE]
        AP[Wi-Fi 6E AP]
    end

    subgraph Offsite
        CLOUD[Backblaze B2 / Wasabi]
    end

  PC -->|10GbE DAC| SW2
  AP -->|2.5GbE trunk| SW2
  NAS2 --> SW2
  NAS2 -->|Nightly encrypted| CLOUD
  UPS2 --> NAS2
```

---

## VLAN plan (homelab)

| VLAN ID | Name | Subnet example | Members | Purpose |
|---------|------|----------------|---------|---------|
| 10 | LAN | 192.168.10.0/24 | PCs, phones, TVs | General |
| 20 | STORAGE | 192.168.20.0/24 | NAS data NIC, 10GbE clients | SMB/NFS/iSCSI |
| 30 | BACKUP | 192.168.30.0/24 | Backup server, NAS backup NIC optional | Restricted |
| 99 | MGMT | 192.168.99.0/24 | IPMI, switch, AP admin | No internet route |

### Firewall rules (summary)

| From | To | Allow |
|------|-----|-------|
| LAN | STORAGE | 445, 2049, 32400 (Plex) |
| LAN | MGMT | Deny (admin jump host only) |
| STORAGE | Internet | Deny (updates via proxy or LAN) |
| BACKUP | STORAGE | rsync/SSH only to backup share |
| Internet | NAS | **Deny** all inbound |

---

## NIC allocation (recommended build)

| Interface | Speed | VLAN | Role |
|-----------|-------|------|------|
| `eth0` (onboard) | 1 GbE | 99 | Management / Unraid WebGUI |
| `bond0` (X550-T2) | 10 GbE ×2 | 20 | Storage; LACP optional |
| IPMI | 1 GbE | 99 | Out-of-band only |

**Homelab simplification:** single 10GbE to switch + 1GbE management on separate subnet without bonding.

---

## Switch port map (example 24-port)

| Ports | Device | Speed |
|-------|--------|-------|
| 1–2 | NAS (LAG) | 10G SFP+ |
| 3 | Workstation | 10G SFP+ |
| 4–8 | 2.5G access | 2.5GBase-T |
| 9–16 | General LAN | 1G |
| 17 | Uplink to router | 10G or 2.5G |
| 18–24 | Spare / AP / IoT | mixed |

---

## Where NAS sits vs backups

```mermaid
sequenceDiagram
    participant C as Client
    participant N as Unraid NAS
    participant L as Local USB HDD
    participant O as Offsite Cloud

    C->>N: Read/write media (VLAN 20)
    N->>L: Nightly rsync (critical shares)
    N->>O: Weekly restic encrypted
    Note over N,O: 3-2-1 satisfied
```

| Role | System | Notes |
|------|--------|-------|
| Primary copy | Unraid array | Live |
| Secondary | USB or 2nd NAS | Same site, different device |
| Tertiary | B2/Wasabi | Encrypted; lifecycle rules |

---

## Remote access

| Method | Use |
|--------|-----|
| WireGuard on router | Remote admin + SMB over VPN |
| Tailscale on NAS | Easy homelab; mind ACLs |
| Cloudflare Tunnel | Web apps only (Notifiarr, etc.) |
| Port-forward SMB | **Avoid** |

---

## DNS and naming

| Host | Example |
|------|---------|
| NAS | `nas.storage.home.arpa` |
| IPMI | `nas-ipmi.mgmt.home.arpa` |
| Static DHCP | Reserve MAC on router or run DHCP on OPNsense |

---

## Cabling checklist

- [ ] Cat6a for 10GBase-T runs < 30 m
- [ ] DAC for rack switch ↔ NAS (< 3 m)
- [ ] Fiber only if electrical isolation needed
- [ ] Separate patch panel label per VLAN color
