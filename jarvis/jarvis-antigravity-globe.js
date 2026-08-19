/**
 * JarvisAntigravityGlobe — holographic cyan orb with antigravity particles.
 * Drop into any Jarvis / voice-assistant UI. Requires Three.js (r160+).
 *
 * Usage:
 *   const globe = new JarvisAntigravityGlobe(document.getElementById('globe'));
 *   globe.setState('listening');
 *   globe.destroy();
 */

const STATES = {
  idle: { pulse: 0.35, speed: 0.45, spread: 1.0, brightness: 0.85, hue: 0.52 },
  listening: { pulse: 0.9, speed: 0.85, spread: 1.12, brightness: 1.25, hue: 0.54 },
  thinking: { pulse: 0.65, speed: 1.35, spread: 1.06, brightness: 1.1, hue: 0.5 },
  speaking: { pulse: 1.1, speed: 0.7, spread: 1.08, brightness: 1.35, hue: 0.56 },
  error: { pulse: 0.55, speed: 0.5, spread: 1.0, brightness: 1.0, hue: 0.0 },
};

function clamp(v, min, max) {
  return Math.min(max, Math.max(min, v));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function fibonacciSphere(count, radius) {
  const points = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < count; i += 1) {
    const y = 1 - (i / (count - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const theta = golden * i;
    points.push(
      Math.cos(theta) * r * radius,
      y * radius,
      Math.sin(theta) * r * radius,
    );
  }
  return points;
}

export class JarvisAntigravityGlobe {
  constructor(container, options = {}) {
    if (!container) throw new Error('JarvisAntigravityGlobe: container element required');
    if (typeof THREE === 'undefined') {
      throw new Error('JarvisAntigravityGlobe: THREE global is required (load Three.js first)');
    }

    this.container = container;
    this.options = {
      particleCount: options.particleCount ?? 2400,
      radius: options.radius ?? 1,
      color: options.color ?? 0x00e5ff,
      accentColor: options.accentColor ?? 0x4df3ff,
      background: options.background ?? 'transparent',
      autoStart: options.autoStart ?? true,
      dprCap: options.dprCap ?? 2,
    };

    this.state = 'idle';
    this.targetState = STATES.idle;
    this.currentState = { ...STATES.idle };
    this.audioLevel = 0;
    this._running = false;
    this._raf = 0;
    this._clock = new THREE.Clock();
    this._resizeObserver = null;

    this._buildScene();
    this._bindEvents();

    if (this.options.autoStart) this.start();
  }

  _buildScene() {
    const { clientWidth: w, clientHeight: h } = this.container;
    const dpr = Math.min(window.devicePixelRatio || 1, this.options.dprCap);

    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: this.options.background === 'transparent',
      powerPreference: 'high-performance',
    });
    this.renderer.setPixelRatio(dpr);
    this.renderer.setSize(Math.max(w, 1), Math.max(h, 1));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.container.appendChild(this.renderer.domElement);
    this.container.classList.add('jarvis-globe-root');

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(42, Math.max(w, 1) / Math.max(h, 1), 0.1, 100);
    this.camera.position.set(0, 0, 4.2);

    this.root = new THREE.Group();
    this.scene.add(this.root);

    this._buildParticles();
    this._buildCore();
    this._buildRings();
    this._buildDust();
    this._buildLights();
  }

  _buildParticles() {
    const count = this.options.particleCount;
    const positions = fibonacciSphere(count, this.options.radius);
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

    const seeds = new Float32Array(count);
    const offsets = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      seeds[i] = Math.random();
      offsets[i * 3] = (Math.random() - 0.5) * 0.35;
      offsets[i * 3 + 1] = Math.random() * 0.5;
      offsets[i * 3 + 2] = (Math.random() - 0.5) * 0.35;
    }
    geometry.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1));
    geometry.setAttribute('aOffset', new THREE.BufferAttribute(offsets, 3));

    this.particleMaterial = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uPulse: { value: 0.35 },
        uSpread: { value: 1 },
        uBrightness: { value: 0.85 },
        uHue: { value: 0.52 },
        uAudio: { value: 0 },
        uColor: { value: new THREE.Color(this.options.color) },
        uAccent: { value: new THREE.Color(this.options.accentColor) },
      },
      vertexShader: `
        attribute float aSeed;
        attribute vec3 aOffset;
        uniform float uTime;
        uniform float uPulse;
        uniform float uSpread;
        uniform float uAudio;
        varying float vGlow;
        varying float vDepth;

        void main() {
          vec3 p = position * uSpread;
          float t = uTime * (0.6 + aSeed * 0.9);
          float lift = sin(t + aSeed * 6.28318) * 0.08;
          float drift = cos(t * 0.7 + aSeed * 12.0) * 0.05;
          p += aOffset;
          p.y += lift + uAudio * 0.12 * aSeed;
          p.x += drift;
          p.z += sin(t * 0.55 + aSeed * 9.0) * 0.04;
          p += normalize(position + vec3(0.0001)) * uPulse * 0.06 * sin(t * 2.0 + aSeed * 20.0);

          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mv;
          float size = 1.6 + aSeed * 2.4 + uAudio * 2.5 + uPulse * 1.5;
          gl_PointSize = size * (220.0 / -mv.z);
          vGlow = 0.35 + aSeed * 0.65 + uPulse * 0.25;
          vDepth = clamp(1.0 - (-mv.z - 2.5) / 3.0, 0.0, 1.0);
        }
      `,
      fragmentShader: `
        uniform float uBrightness;
        uniform float uHue;
        uniform vec3 uColor;
        uniform vec3 uAccent;
        varying float vGlow;
        varying float vDepth;

        vec3 hueShift(vec3 color, float hue) {
          const vec3 k = vec3(0.57735, 0.57735, 0.57735);
          float cosA = cos(hue * 6.28318);
          return color * cosA + cross(k, color) * sin(hue * 6.28318) + k * dot(k, color) * (1.0 - cosA);
        }

        void main() {
          vec2 uv = gl_PointCoord - 0.5;
          float d = length(uv);
          if (d > 0.5) discard;
          float core = smoothstep(0.5, 0.0, d);
          float halo = smoothstep(0.5, 0.08, d);
          vec3 base = mix(uColor, uAccent, vGlow);
          base = hueShift(base, uHue - 0.52);
          vec3 col = base * halo * vGlow * uBrightness * (0.65 + vDepth * 0.35);
          col += base * core * 0.8;
          gl_FragColor = vec4(col, halo * 0.85);
        }
      `,
    });

    this.particles = new THREE.Points(geometry, this.particleMaterial);
    this.root.add(this.particles);
  }

  _buildCore() {
    const geo = new THREE.IcosahedronGeometry(this.options.radius * 0.42, 2);
    this.coreMaterial = new THREE.MeshBasicMaterial({
      color: this.options.color,
      transparent: true,
      opacity: 0.08,
      wireframe: true,
    });
    this.core = new THREE.Mesh(geo, this.coreMaterial);
    this.root.add(this.core);

    const glowGeo = new THREE.SphereGeometry(this.options.radius * 0.55, 32, 32);
    this.glowMaterial = new THREE.MeshBasicMaterial({
      color: this.options.accentColor,
      transparent: true,
      opacity: 0.06,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this.glow = new THREE.Mesh(glowGeo, this.glowMaterial);
    this.root.add(this.glow);
  }

  _buildRings() {
    this.rings = new THREE.Group();
    const ringConfigs = [
      { radius: 1.35, tilt: [0.9, 0.2, 0.1], speed: 0.22 },
      { radius: 1.55, tilt: [-0.5, 0.8, 0.3], speed: -0.16 },
      { radius: 1.75, tilt: [0.2, -0.6, 0.9], speed: 0.12 },
    ];

    ringConfigs.forEach((cfg, index) => {
      const curve = new THREE.EllipseCurve(0, 0, cfg.radius, cfg.radius, 0, Math.PI * 2);
      const points = curve.getPoints(180).map((p) => new THREE.Vector3(p.x, 0, p.y));
      const geo = new THREE.BufferGeometry().setFromPoints(points);
      const mat = new THREE.LineBasicMaterial({
        color: index === 0 ? this.options.accentColor : this.options.color,
        transparent: true,
        opacity: 0.22 + index * 0.06,
        blending: THREE.AdditiveBlending,
      });
      const ring = new THREE.LineLoop(geo, mat);
      ring.rotation.set(cfg.tilt[0], cfg.tilt[1], cfg.tilt[2]);
      ring.userData.speed = cfg.speed;
      this.rings.add(ring);

      const trackerGeo = new THREE.SphereGeometry(0.035, 8, 8);
      const trackerMat = new THREE.MeshBasicMaterial({
        color: this.options.accentColor,
        transparent: true,
        opacity: 0.9,
        blending: THREE.AdditiveBlending,
      });
      const tracker = new THREE.Mesh(trackerGeo, trackerMat);
      tracker.position.set(cfg.radius, 0, 0);
      ring.add(tracker);
      ring.userData.tracker = tracker;
    });

    this.root.add(this.rings);
  }

  _buildDust() {
    const count = 120;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      const r = 1.8 + Math.random() * 1.4;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const mat = new THREE.PointsMaterial({
      color: this.options.accentColor,
      size: 0.03,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this.dust = new THREE.Points(geo, mat);
    this.root.add(this.dust);
  }

  _buildLights() {
    this.scene.add(new THREE.AmbientLight(0x0a1628, 0.8));
    const key = new THREE.PointLight(this.options.color, 1.4, 20);
    key.position.set(2, 2, 3);
    this.scene.add(key);
    const rim = new THREE.PointLight(this.options.accentColor, 0.8, 20);
    rim.position.set(-3, -1, 2);
    this.scene.add(rim);
  }

  _bindEvents() {
    this._onResize = () => this.resize();
    window.addEventListener('resize', this._onResize);
    if (typeof ResizeObserver !== 'undefined') {
      this._resizeObserver = new ResizeObserver(() => this.resize());
      this._resizeObserver.observe(this.container);
    }
  }

  resize() {
    const w = Math.max(this.container.clientWidth, 1);
    const h = Math.max(this.container.clientHeight, 1);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  setState(state) {
    if (!STATES[state]) return this;
    this.state = state;
    this.targetState = STATES[state];
    return this;
  }

  setAudioLevel(level) {
    this.audioLevel = clamp(level, 0, 1);
    return this;
  }

  start() {
    if (this._running) return this;
    this._running = true;
    this._clock.start();
    this._tick();
    return this;
  }

  stop() {
    this._running = false;
    cancelAnimationFrame(this._raf);
    return this;
  }

  _tick = () => {
    if (!this._running) return;
    this._raf = requestAnimationFrame(this._tick);
    const dt = this._clock.getDelta();
    const elapsed = this._clock.elapsedTime;

    const lerpSpeed = 1 - Math.pow(0.001, dt);
    this.currentState.pulse = lerp(this.currentState.pulse, this.targetState.pulse, lerpSpeed);
    this.currentState.speed = lerp(this.currentState.speed, this.targetState.speed, lerpSpeed);
    this.currentState.spread = lerp(this.currentState.spread, this.targetState.spread, lerpSpeed);
    this.currentState.brightness = lerp(this.currentState.brightness, this.targetState.brightness, lerpSpeed);
    this.currentState.hue = lerp(this.currentState.hue, this.targetState.hue, lerpSpeed);

    const audio = this.audioLevel;
    const pulse = this.currentState.pulse + audio * 0.35;
    const speed = this.currentState.speed;

    this.particleMaterial.uniforms.uTime.value = elapsed;
    this.particleMaterial.uniforms.uPulse.value = pulse;
    this.particleMaterial.uniforms.uSpread.value = this.currentState.spread;
    this.particleMaterial.uniforms.uBrightness.value = this.currentState.brightness;
    this.particleMaterial.uniforms.uHue.value = this.currentState.hue;
    this.particleMaterial.uniforms.uAudio.value = audio;

    const floatY = Math.sin(elapsed * 0.55) * 0.04;
    this.root.position.y = floatY;
    this.root.rotation.y += dt * 0.25 * speed;
    this.root.rotation.x = Math.sin(elapsed * 0.35) * 0.08;

    this.core.rotation.y -= dt * 0.4 * speed;
    this.core.rotation.x += dt * 0.2;
    this.coreMaterial.opacity = 0.05 + pulse * 0.05;
    this.glowMaterial.opacity = 0.04 + pulse * 0.05 + audio * 0.04;
    this.glow.scale.setScalar(1 + pulse * 0.08 + audio * 0.12);

    this.rings.children.forEach((ring, i) => {
      ring.rotation.z += dt * ring.userData.speed * speed;
      if (ring.userData.tracker) {
        ring.userData.tracker.material.opacity = 0.55 + pulse * 0.35 + Math.sin(elapsed * 3 + i) * 0.1;
      }
    });

    this.dust.rotation.y += dt * 0.05;
    this.dust.rotation.x += dt * 0.03;

    this.renderer.render(this.scene, this.camera);
  };

  destroy() {
    this.stop();
    window.removeEventListener('resize', this._onResize);
    if (this._resizeObserver) this._resizeObserver.disconnect();

    this.scene.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) {
        if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose());
        else obj.material.dispose();
      }
    });

    this.renderer.dispose();
    if (this.renderer.domElement.parentNode === this.container) {
      this.container.removeChild(this.renderer.domElement);
    }
    this.container.classList.remove('jarvis-globe-root');
  }
}

export default JarvisAntigravityGlobe;
