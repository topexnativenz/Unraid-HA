# Roborock (Saros 10) — Home Assistant

LAN instance: **http://192.168.1.239:8123**

## Current device

| Item | Value |
|------|--------|
| Model | Saros 10 (`roborock.vacuum.a147`) |
| Entity | `vacuum.saros_10` |
| Local IP | `192.168.1.219` (port **58867**) |
| Account | `david@gillespie.kiwi` (Roborock region **US**) |
| Config entry | `01KVZ2T1ZR0GVVGJETJQXCFMQ8` |

## Symptom: integration failed / entities unavailable

UI error: **Failed setup, will retry: No devices were able to successfully setup** (`no_coordinators`).

### Root cause (verified 2026-06-25)

Two issues can appear in sequence:

1. **Expired cloud token** — `RoborockInvalidCredentials` → re-authenticate (email verification code).
2. **Roborock API rate limit** — after reauth or repeated reloads, UI shows **Failed to get Roborock home data** (`home_data_fail`). Roborock allows only **~5 home-data requests per hour**. Setup retries and manual reloads burn this quota quickly.

Network from HA to the vacuum is fine (ping + port 58867 open). With a fresh token, a single API test succeeds; the third call within an hour returns `RoborockRateLimit`.

### Fix: re-authenticate (required when token expired)

1. **Settings → Devices & services → Roborock** (`david@gillespie.kiwi`).
2. **⋮ → Reconfigure** (or **Re-authenticate** if shown).
3. Enter email **`david@gillespie.kiwi`**, region **US**.
4. Enter the **verification code** from your email (Roborock app / account inbox).
5. Wait ~1–2 minutes; confirm `vacuum.saros_10` is no longer `unavailable`.

**Do not** add automations that reload the Roborock integration when unavailable — repeated reloads hit Roborock rate limits and can make recovery worse.

### Fix: rate limited (“Failed to get Roborock home data”)

If reauth succeeded but this message persists:

1. **Stop retrying** — do not reload the integration or restart HA repeatedly.
2. Integration was **disabled** to pause HA’s retry loop (2026-06-25).
3. Wait **at least 1 hour** (Roborock home-data quota resets).
4. **Settings → Devices & services → Roborock → Enable** (one time only).
5. Wait 2–3 minutes; run `roborock_status.py` — expect `loaded` and `vacuum.saros_10` not `unavailable`.

If it fails again after a quiet hour, remove and re-add the integration once (not in a loop).

### Check status (API)

```bash
TOKEN=$(python3 -c "import json; print(json.load(open('/Users/topexnative/.cursor/mcp.json'))['mcpServers']['homeassistant']['headers']['Authorization'].split(' ',1)[1])")
python3 /Users/topexnative/Projects/unraid-array-design/home-assistant/roborock/scripts/roborock_status.py
```

### If reauth does not stick

- Wait 24h before retrying if you see **home data rate limit** errors (max ~5/hour).
- In the Roborock app: confirm the vacuum is online and maps are saved.
- Last resort: remove the integration and add it again (same account); entities may get new IDs — update dashboards/automations.

## HA version

Running **2026.5.1** with `python-roborock==5.5.1` (bundled). Saros 10 local protocol is supported on this version when auth is valid.
