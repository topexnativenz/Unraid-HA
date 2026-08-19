# Jarvis — wake-word activated holographic globe

Software-rendered **Iron Man Jarvis globe** that **activates when you say “Jarvis”** — 3D orange wireframe orb, wake-word listener, voice command capture, and TTS reply (demo).

## Live demo

**https://raw.githack.com/topexnativenz/Unraid-HA/cursor/jarvis-antigravity-globe-2736/jarvis/assistant/index.html**

1. Open in **Chrome or Edge** (Web Speech API required).
2. Click **Enable microphone**.
3. Say **“Jarvis”** — the globe animates in.
4. Say a command — e.g. *“Jarvis, what time is it?”*

> Use the **githack** link above (not jsDelivr `.html` links — those show raw source).

## How it works

| Piece | File |
|-------|------|
| 3D globe render | `jarvis-antigravity-globe.js` |
| Wake word + voice flow | `jarvis-wake-assistant.js` |
| Full-screen assistant UI | `assistant/index.html` |

**Flow:** dormant (black + “Say Jarvis”) → wake word detected → globe fades/scales in → listening → command → thinking → speaking → standby.

## Embed in your Jarvis app

```html
<script type="importmap">
  {
    "imports": {
      "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
      "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
    }
  }
</script>
<script type="module">
  import * as THREE from 'three';
  window.THREE = THREE;
  import JarvisAntigravityGlobe from './jarvis-antigravity-globe.js';
  import JarvisWakeAssistant from './jarvis-wake-assistant.js';

  const globe = new JarvisAntigravityGlobe(document.getElementById('globe'), {
    color: 0xff8c00,
    coreColor: 0xffff00,
    accentColor: 0xffaa00,
    bloom: true,
  });

  const assistant = new JarvisWakeAssistant({
    wakeWord: 'jarvis',
    onWake: () => document.body.classList.add('is-active'),
    onStateChange: (phase) => globe.setState(phase === 'dormant' ? 'idle' : phase),
    onCommand: async (cmd) => {
      globe.setState('thinking');
      // your LLM / home automation here
      globe.setState('speaking');
    },
  });

  document.getElementById('start').onclick = () => assistant.start();
</script>
```

## API

### `JarvisWakeAssistant`

| Method / option | Description |
|-----------------|-------------|
| `wakeWord` | Default `'jarvis'` |
| `start()` | Begin always-on mic + wake-word detection |
| `stop()` | Stop listening |
| `onWake()` | Globe should appear |
| `onCommand(text)` | User command after wake word |
| `onStateChange(phase)` | `dormant`, `activating`, `listening`, `thinking`, `speaking`, `idle` |

### `JarvisAntigravityGlobe`

| Method | Description |
|--------|-------------|
| `setState(state)` | Visual: `idle`, `listening`, `thinking`, `speaking`, `error` |
| `setAudioLevel(0–1)` | Pulse size during TTS / mic |

## Local dev

```bash
cd jarvis && python3 -m http.server 8080
# http://localhost:8080/assistant/
```

## Notes

- **Browser:** Chrome / Edge desktop recommended. Safari/iOS has limited speech recognition.
- **HTTPS:** Mic access needs a secure context (localhost or HTTPS).
- **Wake word:** Uses Web Speech API (cloud in Chrome), not on-device Porcupine. For offline wake word, swap in OpenWakeWord and call `assistant.activate()` from your detector.
- **Manual test:** “Test wake (no mic)” button on the demo page.

## Other files

- `demo/` — manual state buttons (no wake word)
- `docs/physical-levitation-globe.md` — unrelated hardware notes (ignore unless you want a desk toy)
