# Shelly Plus 1 — Wi‑Fi reset after SSID/password change

**Device:** House Garage — Shelly Plus 1 (`shellyplus1-d4d4daf3cabc`, MAC `d4:d4:da:f3:ca:bc`)  
**Home Assistant:** `switch.garage_door_3`  
**Expected setup hotspot name:** `ShellyPlus1-d4d4daf3cabc` (Shelly Plus format: `ShellyPlus1-` + device ID)

Official references:

- [Shelly Plus 1 — button, LED, AP/Bluetooth](https://kb.shelly.cloud/knowledge-base/shelly-plus-1)
- [Add via Bluetooth (Shelly Smart Control)](https://kb.shelly.cloud/knowledge-base/add-via-bluetooth)
- [Add via Wi‑Fi (AP scan)](https://kb.shelly.cloud/knowledge-base/add-via-wi-fi-ap-scan)
- [Shelly Plus web UI — connect to home Wi‑Fi at `192.168.33.1`](https://kb.shelly.cloud/knowledge-base/shelly-plus-plug-it-web-interface-guide) (same flow for all Plus devices)

---

## Before you start

1. **Stand next to the House Garage Shelly** (Bluetooth range ~10 m / 33 ft indoors).
2. **Phone:** Install **Shelly Smart Control** (not the old “Shelly Cloud” app).
3. **Permissions (phone):**
   - **Bluetooth** — required for Method A
   - **Location** — required for Wi‑Fi scanning on Android; often required on iOS for pairing
   - **Local network** (iOS) — required to talk to the device during setup
4. **Home Wi‑Fi:**
   - Shelly Plus 1 supports **2.4 GHz only** (802.11 b/g/n) — not 5 GHz-only SSIDs
   - Have the **new SSID and password** ready (exact spelling, including capitals)
5. **Safety:** You only need to press the **device button** — no need to open mains wiring if the unit is already installed and powered.

---

## LED patterns (red LED) — what you should see

| Pattern | Meaning |
|--------|---------|
| **1 s ON / 1 s OFF** (repeating) | **AP mode** — device hotspot on; Wi‑Fi to router disabled |
| **1 s ON / 3 s OFF** (repeating) | Wi‑Fi enabled but **not connected** to your router |
| **LED constantly ON** | **Connected** to your Wi‑Fi |
| **½ s ON / ½ s OFF** (while holding button) | Button held ~5 s — entering AP + Bluetooth |
| **¼ s ON / ¼ s OFF** (while holding button) | Button held ~10 s — factory reset in progress |

---

## Step 1 — Wake AP + Bluetooth (do this first)

On the **Shelly Plus 1** at the house garage:

1. Confirm the device has **power** (LED may be off, flashing, or solid depending on old Wi‑Fi).
2. **Press and hold the single button for 5 seconds**, then release.
3. Within ~30 s the LED should show **AP mode**: **1 second ON / 1 second OFF** repeating.
4. On your phone’s Wi‑Fi list, look for a network named like **`ShellyPlus1-d4d4daf3cabc`** (may take up to a minute).

If you never see that hotspot or Bluetooth discovery, try **Step 6 (factory reset)** only after Methods A–C fail.

---

## Method A — Shelly Smart Control + Bluetooth (recommended)

1. Enable **Bluetooth** on your phone.
2. Open **Shelly Smart Control** → sign in to your Shelly account.
3. Tap **+** (Add device) → choose **Add via Bluetooth**.
4. Tap **Next**. Wait for the device list — select **`shellyplus1-d4d4daf3cabc`** (or the Plus 1 entry with MAC ending `…cabc`).
5. Tap **Next**.
6. Enter your **new 2.4 GHz Wi‑Fi SSID** and **password** → tap **+ Add device**.
7. Wait **2–5 minutes** (official docs note it can take a few minutes). Success message should appear when the device joins Wi‑Fi.
8. Name the device (e.g. “House Garage Door”) → assign a room → **Save**.

**Success check:** LED goes **constantly ON** (connected to Wi‑Fi).

---

## Method B — Shelly Smart Control + Wi‑Fi AP scan

Use this if Bluetooth discovery fails but you see the **`ShellyPlus1-…`** hotspot.

1. Complete **Step 1** (5 s button hold) so AP mode is active.
2. In **Shelly Smart Control** → **+** → **Add via Wi‑Fi (AP scan)**.
3. Tap **Next** → select **`ShellyPlus1-d4d4daf3cabc`** (or matching entry).
4. Tap **Next** → confirm or **Edit** the target home network → enter **new SSID/password** → **Add device**.
5. Wait until pairing completes; LED should become **constantly ON**.

---

## Method C — Phone browser via device hotspot (no Bluetooth)

1. Complete **Step 1** (5 s hold, AP LED **1 s ON / 1 s OFF**).
2. On the phone, open **Settings → Wi‑Fi** and join **`ShellyPlus1-d4d4daf3cabc`** (no internet on this network is normal).
3. Open a browser and go to: **`http://192.168.33.1`**
4. Go to **Settings → Wi‑Fi** (or **Networks**).
5. **Enable Wi‑Fi 1**, select your **2.4 GHz** home SSID, enter the **new password**, **Save**.
6. Wait ~30 s. The page should show a **new IP address** link when connected — note that IP (e.g. `192.168.1.xxx`).
7. Reconnect your phone to your **normal home Wi‑Fi**, then open the new IP in the browser to confirm the device is online.

Optional but recommended: set a **static IP** or DHCP reservation on your router for this MAC (`d4:d4:da:f3:ca:bc`) so Home Assistant always finds it.

---

## Step 6 — Factory reset (only if A–C cannot see the device)

**Warning:** Factory reset clears device settings. Home Assistant usually recovers the same `switch.garage_door_3` entity after the integration reconnects, but confirm in HA after setup.

1. **Press and hold the button for 10 seconds** (LED shows **¼ s ON / ¼ s OFF** while holding).
2. Release. Device resets; after reboot it should enter **AP mode** (**1 s ON / 1 s OFF**).
3. Run **Method A** or **Method B** from scratch as if it were a new device.

---

## Verify the device is on your LAN

From a computer or phone on home Wi‑Fi:

```bash
# Replace with IP from Shelly web UI if you noted it
curl -sS -X POST "http://192.168.1.XXX/rpc/Shelly.GetDeviceInfo" -d '{}'
```

You should see JSON with `"id":"shellyplus1-d4d4daf3cabc"` (or similar).

Or check your router’s DHCP/client list for MAC **`d4:d4:da:f3:ca:bc`**.

---

## Reconnect Home Assistant

After the Shelly is on Wi‑Fi and reachable:

1. Open **`http://192.168.1.239:8123`**
2. **Settings → Devices & services → Shelly**
3. Find **`shellyplus1-d4d4daf3cabc`** (House Garage Door)
   - If it shows an error: open the device → **Reload** (or three-dot menu → **Reload**)
   - If still failing: **Disable** then **Enable** the config entry
4. **Developer tools → States** → confirm **`switch.garage_door_3`** is `on` or `off`, **not** `unavailable`
5. On the **Mobile Home** app, open **Garage & Doors** → **House Garage** should respond (card uses `switch.garage_door_3`)

No dashboard YAML change is required if the entity recovers with the same ID.

---

## Troubleshooting

| Problem | What to try |
|--------|-------------|
| No `ShellyPlus1-…` Wi‑Fi | Power-cycle the Shelly; repeat **5 s** button hold; check LED |
| Wrong password | LED stays **1 s ON / 3 s OFF** — re-enter Wi‑Fi credentials in app or at `192.168.33.1` |
| Only 5 GHz Wi‑Fi | Create or use a **2.4 GHz** SSID (or enable “Smart connect” / separate 2.4 GHz name on router) |
| Bluetooth list empty | Use **Method B** or **C**; confirm Bluetooth permission for Shelly Smart Control |
| iOS won’t pair | Settings → Shelly Smart Control → enable **Local Network** + **Bluetooth** |
| HA still `unavailable` | Confirm device IP on LAN → reload Shelly integration → restart Home Assistant core if needed |
| Weak signal at garage | Move AP closer, add a 2.4 GHz mesh node, or use Shelly’s second Wi‑Fi slot (Wi‑Fi 2) for a closer SSID |

---

## Quick reference — one button, two holds

| Hold time | Action |
|-----------|--------|
| **5 seconds** | Enable **AP + Bluetooth** (use after Wi‑Fi password change) |
| **10 seconds** | **Factory reset** (last resort) |
