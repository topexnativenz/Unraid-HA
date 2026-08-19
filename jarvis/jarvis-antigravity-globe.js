/**
 * JarvisAntigravityGlobe — Iron Man HUD holographic orb.
 * Orange wireframe core, radial spikes, thick orbital ribbons, particle rings, bloom.
 */

const STATES = {
  idle: { pulse: 0.4, speed: 0.5, spread: 1.0, brightness: 1.0, bloom: 1.2, hue: 0.08 },
  listening: { pulse: 0.95, speed: 0.85, spread: 1.08, brightness: 1.35, bloom: 1.6, hue: 0.1 },
  thinking: { pulse: 0.7, speed: 1.4, spread: 1.04, brightness: 1.15, bloom: 1.4, hue: 0.06 },
  speaking: { pulse: 1.15, speed: 0.75, spread: 1.06, brightness: 1.5, bloom: 1.75, hue: 0.12 },
  error: { pulse: 0.55, speed: 0.45, spread: 1.0, brightness: 1.0, bloom: 1.1, hue: 0.0 },
};

function clamp(v, min, max) {
  return Math.min(max, Math.max(min, v));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

export class JarvisAntigravityGlobe {
  constructor(container, options = {}) {
    if (!container) throw new Error('JarvisAntigravityGlobe: container element required');
    if (typeof THREE === 'undefined') {
      throw new Error('JarvisAntigravityGlobe: THREE global is required (load Three.js first)');
    }

    this.container = container;
    this.options = {
      radius: options.radius ?? 1,
      color: options.color ?? 0xff8c00,
      coreColor: options.coreColor ?? 0xffff00,
      accentColor: options.accentColor ?? 0xffaa00,
      background: options.background ?? 'transparent',
      autoStart: options.autoStart ?? true,
      dprCap: options.dprCap ?? 2,
      bloom: options.bloom ?? true,
      spikeCount: options.spikeCount ?? 18,
    };

    this.state = 'idle';
    this.targetState = STATES.idle;
    this.currentState = { ...STATES.idle };
    this.audioLevel = 0;
    this._running = false;
    this._raf = 0;
    this._clock = new THREE.Clock();
    this._resizeObserver = null;
    this._composer = null;

    this._buildScene();
    this._bindEvents();
    if (this.options.autoStart) this.start();
  }

  async _initBloom() {
    if (!this.options.bloom || this._composer) return;
    try {
      const { EffectComposer } = await import('three/addons/postprocessing/EffectComposer.js');
      const { RenderPass } = await import('three/addons/postprocessing/RenderPass.js');
      const { UnrealBloomPass } = await import('three/addons/postprocessing/UnrealBloomPass.js');

      const w = Math.max(this.container.clientWidth, 1);
      const h = Math.max(this.container.clientHeight, 1);
      this._composer = new EffectComposer(this.renderer);
      this._composer.addPass(new RenderPass(this.scene, this.camera));
      this._bloomPass = new UnrealBloomPass(new THREE.Vector2(w, h), 1.2, 0.45, 0.15);
      this._composer.addPass(this._bloomPass);
    } catch {
      this._composer = null;
    }
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
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;
    this.container.appendChild(this.renderer.domElement);
    this.container.classList.add('jarvis-globe-root');

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(38, Math.max(w, 1) / Math.max(h, 1), 0.1, 100);
    this.camera.position.set(0, 0, 4.8);

    this.root = new THREE.Group();
    this.scene.add(this.root);

    this._buildCore();
    this._buildWireframe();
    this._buildSpikes();
    this._buildRibbons();
    this._buildParticleRings();
    this._buildOuterDust();
    this._buildLights();

    this._initBloom();
  }

  _buildCore() {
    const r = this.options.radius * 0.18;
    const geo = new THREE.SphereGeometry(r, 24, 24);
    this.coreMat = new THREE.MeshBasicMaterial({
      color: this.options.coreColor,
      transparent: true,
      opacity: 0.95,
    });
    this.core = new THREE.Mesh(geo, this.coreMat);
    this.root.add(this.core);

    const haloGeo = new THREE.SphereGeometry(r * 2.2, 24, 24);
    this.haloMat = new THREE.MeshBasicMaterial({
      color: this.options.accentColor,
      transparent: true,
      opacity: 0.25,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this.halo = new THREE.Mesh(haloGeo, this.haloMat);
    this.root.add(this.halo);
  }

  _buildWireframe() {
    const geo = new THREE.IcosahedronGeometry(this.options.radius * 0.72, 2);
    this.wireMat = new THREE.MeshBasicMaterial({
      color: this.options.color,
      wireframe: true,
      transparent: true,
      opacity: 0.85,
    });
    this.wireframe = new THREE.Mesh(geo, this.wireMat);
    this.root.add(this.wireframe);
  }

  _buildSpikes() {
    const count = this.options.spikeCount;
    const inner = this.options.radius * 0.15;
    const outer = this.options.radius * 2.35;
    const positions = [];
    const golden = Math.PI * (3 - Math.sqrt(5));

    for (let i = 0; i < count; i += 1) {
      const y = 1 - (i / (count - 1)) * 2;
      const r = Math.sqrt(Math.max(0, 1 - y * y));
      const theta = golden * i;
      const dx = Math.cos(theta) * r;
      const dy = y;
      const dz = Math.sin(theta) * r;
      positions.push(0, 0, 0, dx * outer, dy * outer, dz * outer);
      positions.push(dx * inner, dy * inner, dz * inner, dx * outer, dy * outer, dz * outer);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    this.spikeMat = new THREE.LineBasicMaterial({
      color: this.options.color,
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
    });
    this.spikes = new THREE.LineSegments(geo, this.spikeMat);
    this.root.add(this.spikes);
  }

  _buildRibbons() {
    this.ribbons = new THREE.Group();
    const configs = [
      { radius: 1.55, tube: 0.055, tilt: [1.1, 0.3, 0.2], speed: 0.18, arc: Math.PI * 1.35 },
      { radius: 1.72, tube: 0.048, tilt: [-0.6, 0.9, 0.5], speed: -0.14, arc: Math.PI * 1.2 },
    ];

    configs.forEach((cfg, idx) => {
      const points = [];
      const segments = 80;
      for (let i = 0; i <= segments; i += 1) {
        const t = (i / segments) * cfg.arc - cfg.arc * 0.5;
        points.push(new THREE.Vector3(Math.cos(t) * cfg.radius, Math.sin(t) * cfg.radius * 0.35, Math.sin(t) * cfg.radius * 0.65));
      }
      const curve = new THREE.CatmullRomCurve3(points);
      const geo = new THREE.TubeGeometry(curve, 64, cfg.tube, 8, false);
      const mat = new THREE.MeshBasicMaterial({
        color: idx === 0 ? this.options.accentColor : this.options.color,
        transparent: true,
        opacity: 0.55,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        side: THREE.DoubleSide,
      });
      const ribbon = new THREE.Mesh(geo, mat);
      ribbon.rotation.set(cfg.tilt[0], cfg.tilt[1], cfg.tilt[2]);
      ribbon.userData.speed = cfg.speed;
      this.ribbons.add(ribbon);
    });

    this.root.add(this.ribbons);
  }

  _buildParticleRings() {
    this.particleRings = new THREE.Group();
    const ringConfigs = [
      { radius: 1.15, count: 220, tilt: [0.4, 0.1, 0.2], speed: 0.25 },
      { radius: 1.35, count: 180, tilt: [1.0, 0.5, 0.0], speed: -0.2 },
      { radius: 1.55, count: 140, tilt: [-0.3, 0.8, 0.6], speed: 0.15 },
      { radius: 1.85, count: 100, tilt: [0.2, -0.5, 1.0], speed: -0.12 },
    ];

    ringConfigs.forEach((cfg) => {
      const positions = new Float32Array(cfg.count * 3);
      const seeds = new Float32Array(cfg.count);
      for (let i = 0; i < cfg.count; i += 1) {
        const angle = (i / cfg.count) * Math.PI * 2;
        const wobble = (Math.random() - 0.5) * 0.08;
        positions[i * 3] = Math.cos(angle) * (cfg.radius + wobble);
        positions[i * 3 + 1] = (Math.random() - 0.5) * 0.06;
        positions[i * 3 + 2] = Math.sin(angle) * (cfg.radius + wobble);
        seeds[i] = Math.random();
      }

      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geo.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1));

      const mat = new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms: {
          uTime: { value: 0 },
          uPulse: { value: 0.4 },
          uAudio: { value: 0 },
          uColor: { value: new THREE.Color(this.options.accentColor) },
          uCore: { value: new THREE.Color(this.options.coreColor) },
        },
        vertexShader: `
          attribute float aSeed;
          uniform float uTime;
          uniform float uPulse;
          uniform float uAudio;
          varying float vGlow;
          void main() {
            vec3 p = position;
            float t = uTime * (0.5 + aSeed);
            p.y += sin(t + aSeed * 6.28) * 0.04 + uAudio * 0.08;
            p += normalize(p + 0.001) * uPulse * 0.03 * sin(t * 2.0);
            vec4 mv = modelViewMatrix * vec4(p, 1.0);
            gl_Position = projectionMatrix * mv;
            gl_PointSize = (1.5 + aSeed * 2.5 + uPulse * 1.2 + uAudio * 2.0) * (180.0 / -mv.z);
            vGlow = 0.4 + aSeed * 0.6;
          }
        `,
        fragmentShader: `
          uniform vec3 uColor;
          uniform vec3 uCore;
          varying float vGlow;
          void main() {
            vec2 uv = gl_PointCoord - 0.5;
            float d = length(uv);
            if (d > 0.5) discard;
            float glow = smoothstep(0.5, 0.0, d);
            vec3 col = mix(uColor, uCore, glow * vGlow);
            gl_FragColor = vec4(col * glow * vGlow * 1.4, glow * 0.9);
          }
        `,
      });

      const ring = new THREE.Points(geo, mat);
      ring.rotation.set(cfg.tilt[0], cfg.tilt[1], cfg.tilt[2]);
      ring.userData.speed = cfg.speed;
      ring.userData.material = mat;
      this.particleRings.add(ring);
    });

    this.root.add(this.particleRings);
  }

  _buildOuterDust() {
    const count = 90;
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      const r = 2.0 + Math.random() * 0.8;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    this.dustMat = new THREE.PointsMaterial({
      color: this.options.accentColor,
      size: 0.025,
      transparent: true,
      opacity: 0.4,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this.dust = new THREE.Points(geo, this.dustMat);
    this.root.add(this.dust);
  }

  _buildLights() {
    this.scene.add(new THREE.AmbientLight(0x1a0a00, 0.6));
    const core = new THREE.PointLight(this.options.coreColor, 2.5, 12);
    core.position.set(0, 0, 0);
    this.root.add(core);
    const rim = new THREE.PointLight(this.options.color, 1.2, 20);
    rim.position.set(3, 2, 4);
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
    if (this._composer) {
      this._composer.setSize(w, h);
      if (this._bloomPass) this._bloomPass.resolution.set(w, h);
    }
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
    for (const key of Object.keys(this.currentState)) {
      this.currentState[key] = lerp(this.currentState[key], this.targetState[key], lerpSpeed);
    }

    const audio = this.audioLevel;
    const pulse = this.currentState.pulse + audio * 0.4;
    const speed = this.currentState.speed;
    const spread = this.currentState.spread;

    this.root.position.y = Math.sin(elapsed * 0.5) * 0.03;
    this.root.rotation.y += dt * 0.2 * speed;
    this.root.rotation.x = Math.sin(elapsed * 0.3) * 0.06;
    this.root.scale.setScalar(spread);

    this.coreMat.opacity = 0.85 + pulse * 0.1;
    this.haloMat.opacity = 0.18 + pulse * 0.12 + audio * 0.1;
    this.halo.scale.setScalar(1 + pulse * 0.15 + audio * 0.2);
    this.wireMat.opacity = 0.65 + pulse * 0.2;
    this.wireframe.rotation.y += dt * 0.35 * speed;
    this.wireframe.rotation.x += dt * 0.15;
    this.spikeMat.opacity = 0.55 + pulse * 0.25;

    this.ribbons.children.forEach((ribbon) => {
      ribbon.rotation.z += dt * ribbon.userData.speed * speed;
      ribbon.material.opacity = 0.4 + pulse * 0.2;
    });

    this.particleRings.children.forEach((ring) => {
      ring.rotation.z += dt * ring.userData.speed * speed;
      const mat = ring.userData.material;
      mat.uniforms.uTime.value = elapsed;
      mat.uniforms.uPulse.value = pulse;
      mat.uniforms.uAudio.value = audio;
    });

    this.dust.rotation.y += dt * 0.04;
    this.dust.rotation.x += dt * 0.025;

    if (this._bloomPass) {
      this._bloomPass.strength = this.currentState.bloom + audio * 0.35;
    }

    if (this._composer) {
      this._composer.render();
    } else {
      this.renderer.render(this.scene, this.camera);
    }
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

    if (this._composer) this._composer.dispose();
    this.renderer.dispose();
    if (this.renderer.domElement.parentNode === this.container) {
      this.container.removeChild(this.renderer.domElement);
    }
    this.container.classList.remove('jarvis-globe-root');
  }
}

export default JarvisAntigravityGlobe;
