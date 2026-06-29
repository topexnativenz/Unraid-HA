# Home Assistant (Three Mile Bush)

LAN instance: **http://192.168.1.239:8123**

| Area | Doc |
|------|-----|
| Gate (Akuvox, approach zones) | [gate/README.md](gate/README.md) |
| Gate reliability strategy | [docs/gate-approach-strategy.md](../docs/gate-approach-strategy.md) |
| Mobile Home dashboard | [mobile-dashboard/README.md](mobile-dashboard/README.md) |
| Tablet dashboard | [tablet-dashboard/README.md](tablet-dashboard/README.md) |
| Solar dashboard | [solar-dashboard/README.md](solar-dashboard/README.md) |
| Casa Luna (side / experimental) | [casa-luna/README.md](casa-luna/README.md) |
| G-UNIT 16:9 wall tablet (1920×1080) | [casa-luna-16x9/README.md](casa-luna-16x9/README.md) |
| Garage doors (Tapo sensor, Model S automations) | [garage-doors/README.md](garage-doors/README.md) |
| Roborock (Saros 10) | [roborock/README.md](roborock/README.md) |

---

## Companion app — remote access (Nabu Casa)

**Primary path for Dave + Gen phones:** [Home Assistant Cloud](https://www.nabucasa.com/) (Nabu Casa). Do **not** use Tailscale on phones for Companion — Tailscale stays for **tower / Unraid admin** only ([docs/05-network-and-layout.md](../docs/05-network-and-layout.md)).

Why Nabu Casa for Companion:

- First-party HTTPS relay (SniTun); no VPN app on the phone
- Survives HA updates without Tailscale add-on / subnet-route breakage
- Companion app supports **Use Home Assistant Cloud** natively
- Location updates and push notifications work over the cloud path

### One-time — Home Assistant server

1. **Settings → Home Assistant Cloud** (or **Settings → Cloud**).
2. Sign in / create Nabu Casa account and **start subscription** (~US$6.50/mo).
3. Enable **Remote UI** (should show connected; entity `binary_sensor.remote_ui` → `on`).
4. **Settings → System → Network:**
   - **Local network URL:** `http://192.168.1.239:8123`
   - **Home network Wi‑Fi SSID(s):** your home SSID(s) so the app uses LAN at home and cloud when away.
5. Optional YAML (normally set by the Cloud UI):

   ```yaml
   homeassistant:
     internal_url: "http://192.168.1.239:8123"
     # external_url is set automatically when Remote UI is connected
   ```

6. After changes: **Developer tools → YAML → Reload location & network** (or restart HA).

### Per phone — Companion app checklist

Do on **Dave (Halo)** and **Gen (Gens phone)**:

| Step | Where | Value |
|------|--------|-------|
| 1. Connect | First open or **App Configuration → Companion App → Re-register** | Sign in with the same HA user as on the web UI |
| 2. Internal URL | **App Configuration → Connection → Internal Connection URL** | `http://192.168.1.239:8123` |
| 3. Home SSID | **App Configuration → Connection → Home network SSID** | Your home Wi‑Fi name (exact match) |
| 4. Cloud | **App Configuration → Connection → Use Home Assistant Cloud** | **On** |
| 5. Remove Tailscale URL | **App Configuration → Connection** | Clear any **External** / custom URL pointing at `100.x.x.x` or Tailscale MagicDNS |
| 6. Location | iOS **Settings → Home Assistant → Location → Always** | Required for gate Road Approach |
| 7. Background location | Companion **App Configuration → Location** | Background updates **on**; **Location submission: Always** (recommended) |
| 8. Zones | Companion **App Configuration → Location → Manage zones** | Re-sync **Home**, **Road Approach**, **Gate Approach** |
| 9. Notifications | Allow notifications for the app | Gate / garage alerts |
| 10. Dashboard | See [mobile-dashboard/README.md](mobile-dashboard/README.md) | **Mobile Home** as device default |

**Remove Tailscale from Companion workflow (keep Tailscale app for tower SSH only):**

- Do **not** connect Companion via `http://100.x.x.x:8123` or Tailscale Serve URLs.
- On iPhone: you can leave Tailscale installed for admin; disable **Use Tailscale** / exit the VPN before relying on Companion if iOS routes HA traffic through a broken tunnel.
- If you previously added a **Siri Shortcut** or **Automation** with a Tailscale URL, change deep links to `homeassistant://` or the Nabu Casa HTTPS URL from **Settings → Home Assistant Cloud → Remote UI** link.

### Verify remote access

1. Turn **Wi‑Fi off** on the phone (LTE only), open Companion — should connect without Tailscale.
2. **Developer tools → States** → `device_tracker.halo` / `device_tracker.gens_phone` — `source_type: gps`, state updates when moving.
3. Tap a gate / garage / light action remotely — should respond within a few seconds.
4. Drive home once — check `input_text.gate_status_message` for `halo_enter_road` or Tessie trigger ([gate README](gate/README.md)).

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| App stuck on old URL after network change | **Reset Frontend Cache** (Companion → Debugging), force-quit, reopen |
| Works on Wi‑Fi, fails on cellular | Confirm **Use Home Assistant Cloud** on; Remote UI connected in HA |
| Location not updating away from home | Location **Always** + **Location submission: Always**; not Tailscale |
| Still tries Tailscale | Remove custom external URL; sign out/in Companion; re-register app |

Network layout context: [docs/05-network-and-layout.md](../docs/05-network-and-layout.md) — Tailscale for NAS/tower admin, Nabu Casa for HA Companion.
