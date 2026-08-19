# Jarvis Antigravity Globe

Holographic cyan orb for a Jarvis-style AI assistant — floating particle shell, orbital rings, and state-driven pulse (idle, listening, thinking, speaking, error).

Inspired by voice-assistant demos like [this Short](https://youtube.com/shorts/V6kvapGV9qk).

## Live demo

**https://topexnativenz.github.io/Unraid-HA/demo/**

Works on phone and desktop — open the link in Safari or Chrome. Tap the state buttons to preview orb reactions.

> If the link 404s right after merge, wait ~1 minute for GitHub Pages to finish deploying (Actions tab → **Deploy Jarvis Demo**).

## Local demo (optional)

```bash
cd jarvis
python3 -m http.server 8080
```

Open [http://localhost:8080/demo/](http://localhost:8080/demo/).

## Install in your app

1. Copy `jarvis-antigravity-globe.js` and `jarvis-antigravity-globe.css`.
2. Load Three.js (r160+).
3. Mount the globe on a container element.

```html
<link rel="stylesheet" href="/jarvis/jarvis-antigravity-globe.css" />
<div id="jarvis-orb" style="width:320px;height:320px"></div>

<script type="module">
  import * as THREE from 'three';
  window.THREE = THREE;
  import JarvisAntigravityGlobe from '/jarvis/jarvis-antigravity-globe.js';

  const globe = new JarvisAntigravityGlobe(document.getElementById('jarvis-orb'));

  // Hook into your assistant lifecycle
  globe.setState('listening');
  globe.setAudioLevel(0.6); // 0–1 mic / TTS level
  globe.setState('thinking');
  globe.setState('speaking');
  globe.setState('idle');
</script>
```

## API

| Method | Description |
|--------|-------------|
| `new JarvisAntigravityGlobe(container, options?)` | Create orb in a DOM element |
| `setState(state)` | `'idle' \| 'listening' \| 'thinking' \| 'speaking' \| 'error'` |
| `setAudioLevel(0–1)` | Drive pulse size from mic or playback level |
| `start()` / `stop()` | Pause/resume render loop |
| `resize()` | Call after container size changes |
| `destroy()` | Cleanup WebGL + listeners |

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `particleCount` | `2400` | Shell particle density |
| `radius` | `1` | Base sphere radius |
| `color` | `0x00e5ff` | Primary cyan |
| `accentColor` | `0x4df3ff` | Highlight cyan |
| `background` | `'transparent'` | Renderer clear color |
| `autoStart` | `true` | Begin animation immediately |

## Integration tips

- **Voice wake:** `setState('listening')` when the wake word fires.
- **LLM request:** `setState('thinking')` while waiting for a response.
- **TTS playback:** `setState('speaking')` and feed `setAudioLevel()` from analyser node.
- **Desktop overlay:** use a small fixed-size div (e.g. 64×64) in a corner — same API.
- **React / Vue:** instantiate in `useEffect` / `onMounted`, call `destroy()` on unmount.

## Files

```
jarvis/
├── jarvis-antigravity-globe.js   # Main class (ES module)
├── jarvis-antigravity-globe.css  # Container + optional demo HUD styles
├── demo/index.html               # Interactive preview
└── README.md
```
