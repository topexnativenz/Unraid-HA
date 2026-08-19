# Jarvis — wake-word activated holographic globe

Software-rendered **Jarvis globe** with two integration modes:

| Mode | Entry | Use case |
|------|-------|----------|
| **Wake-word UI** | `assistant/index.html` | Say “Jarvis” → globe appears (browser mic) |
| **WebSocket globe** | `globe-interface/index.html` | Python backend drives spin / pulse / speak |

---

## WebSocket globe (Python backend)

Cyber neon wireframe globe — spins to coordinates, pulses when talking. Connects to `ws://localhost:8765`.

### Quick start

```bash
cd jarvis
chmod +x run-globe-stack.sh
./run-globe-stack.sh
```

Open **http://localhost:8080/globe-interface/**

In the Python terminal, type:

- `scan` — spin to London (51.50, -0.12)
- `goto 40.71 -74.01` — spin to custom lat/lon
- `speak` — pulse while “speaking”
- `listen` — HUD state → listening

### Manual start

```bash
pip install -r jarvis/backend/requirements.txt
python3 jarvis/backend/jarvis_globe_server.py
# separate terminal:
cd jarvis && python3 -m http.server 8080
```

### WebSocket payload examples

```json
{"action": "scan_location", "lat": 51.5, "lon": -0.12}
{"action": "speaking", "active": true}
{"action": "pulse", "duration_ms": 800, "opacity": 1.0}
{"action": "set_state", "state": "listening"}
```

Pipe these from your speech loop, FastAPI app, or Home Assistant automation.

---

## Wake-word assistant (browser only)

**https://raw.githack.com/topexnativenz/Unraid-HA/cursor/jarvis-antigravity-globe-2736/jarvis/assistant/index.html**

1. Chrome/Edge → **Enable microphone**
2. Say **“Jarvis”** → orange 3D orb animates in
3. Say a command

Files: `jarvis-antigravity-globe.js`, `jarvis-wake-assistant.js`, `assistant/index.html`

---

## Embed WebSocket globe in your assistant

```python
import asyncio, json, websockets

async def notify_globe(action, **kwargs):
    async with websockets.connect("ws://localhost:8765") as ws:
        await ws.send(json.dumps({"action": action, **kwargs}))

# on wake word:
asyncio.run(notify_globe("set_state", state="listening"))
# on TTS start:
asyncio.run(notify_globe("speaking", active=True))
```

---

## Local dev (wake-word orb)

```bash
cd jarvis && python3 -m http.server 8080
# http://localhost:8080/assistant/
```
