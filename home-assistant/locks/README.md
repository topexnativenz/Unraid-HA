# Schlage Encode Plus — Home Assistant

LAN Home Assistant: **http://192.168.1.239:8123** · timezone **Pacific/Auckland**

## Connect the lock

The **Schlage** integration is already added on HA (`david@gillespie.kiwi`) but shows **no devices** yet. Finish pairing in the Schlage app first:

1. Install **Schlage Home** on your phone.
2. Add the **Encode Plus** to your Schlage account (2.4 GHz Wi‑Fi).
3. Confirm the lock appears in the Schlage app (lock/unlock works remotely).
4. In HA: **Settings → Devices & services → Schlage** → **⋮ → Reload**.
5. **Developer tools → States** — filter `lock.` and note the new entity (often `lock.front_door`).
6. If the entity ID differs, update `entity_id: lock.front_door` in `automations/schlage.yaml` and redeploy.

Official integration: [home-assistant.io/integrations/schlage](https://www.home-assistant.io/integrations/schlage/)

### Apple Home / HomeKey

If the lock is paired to Apple Home only, HA’s Schlage cloud integration will not see it. Options:

- Also add the lock to the **Schlage app** (Wi‑Fi) for HA cloud control, or
- Use a HomeKit bridge workflow (see [community guide](https://community.home-assistant.io/t/schlage-encode-plus-in-apple-home-w-homekey-and-home-assistant/684159)).

## Automation (repo-managed)

| ID | Alias | Behaviour |
|----|-------|-----------|
| `schlage_lock_at_9pm` | Schlage — lock at 9 PM | Daily **21:00** NZ time; locks only if state is `unlocked` |

To lock at **09:00** instead, change `at: "21:00:00"` in `automations/schlage.yaml` to `at: "09:00:00"`.

## Deploy

```bash
/Users/topexnative/Projects/unraid-array-design/home-assistant/locks/scripts/deploy_locks.sh
```

Copies the locks automation block into `/config/automations.yaml` (SMB when available), then reloads HA.

## Verify

```bash
TOKEN=$(python3 -c "import json;from pathlib import Path;d=json.loads(Path('/Users/topexnative/.cursor/mcp.json').read_text());print(d['mcpServers']['homeassistant']['headers']['Authorization'].split(' ',1)[1])")

curl -sS -H "Authorization: Bearer $TOKEN" http://192.168.1.239:8123/api/states/lock.front_door
curl -sS -H "Authorization: Bearer $TOKEN" http://192.168.1.239:8123/api/states/automation.schlage_lock_at_9_pm
```
