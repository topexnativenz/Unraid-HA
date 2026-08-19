/**
 * JarvisWakeAssistant — wake-word activated Jarvis globe.
 * Listens for "Jarvis" (Web Speech API), reveals the 3D orb, captures a command.
 */

const SpeechRecognition = typeof window !== 'undefined'
  && (window.SpeechRecognition || window.webkitSpeechRecognition);

export class JarvisWakeAssistant {
  constructor(options = {}) {
    this.wakeWord = (options.wakeWord ?? 'jarvis').toLowerCase();
    this.lang = options.lang ?? (typeof navigator !== 'undefined' ? navigator.language : 'en-US');
    this.idleTimeoutMs = options.idleTimeoutMs ?? 12000;
    this.commandSilenceMs = options.commandSilenceMs ?? 1800;

    this.onWake = options.onWake ?? (() => {});
    this.onCommand = options.onCommand ?? (() => {});
    this.onStateChange = options.onStateChange ?? (() => {});
    this.onTranscript = options.onTranscript ?? (() => {});
    this.onError = options.onError ?? (() => {});

    this._active = false;
    this._listening = false;
    this._commandMode = false;
    this._recognition = null;
    this._idleTimer = null;
    this._commandBuffer = '';
    this._lastCommandAt = 0;
    this._supported = Boolean(SpeechRecognition);
  }

  get supported() {
    return this._supported;
  }

  get active() {
    return this._active;
  }

  _setPhase(phase) {
    this.onStateChange(phase);
  }

  _clearIdleTimer() {
    if (this._idleTimer) {
      clearTimeout(this._idleTimer);
      this._idleTimer = null;
    }
  }

  _armIdleTimer() {
    this._clearIdleTimer();
    this._idleTimer = setTimeout(() => this.deactivate(), this.idleTimeoutMs);
  }

  _normalize(text) {
    return text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
  }

  _containsWakeWord(text) {
    const n = this._normalize(text);
    return n === this.wakeWord
      || n.startsWith(`${this.wakeWord} `)
      || n.includes(` ${this.wakeWord} `)
      || n.endsWith(` ${this.wakeWord}`);
  }

  _extractCommand(text) {
    const n = this._normalize(text);
    const re = new RegExp(`\\b${this.wakeWord}\\b`, 'gi');
    return n.replace(re, ' ').replace(/\s+/g, ' ').trim();
  }

  activate(fromWake = true) {
    if (this._active) {
      this._armIdleTimer();
      return;
    }
    this._active = true;
    this._commandMode = true;
    this._commandBuffer = '';
    this._setPhase('activating');
    if (fromWake) this.onWake();

    window.setTimeout(() => {
      this._setPhase('listening');
      this._armIdleTimer();
    }, 650);
  }

  deactivate() {
    this._clearIdleTimer();
    this._active = false;
    this._commandMode = false;
    this._commandBuffer = '';
    this._setPhase('dormant');
  }

  simulateWake() {
    this.activate(true);
  }

  _handleTranscript(raw, isFinal) {
    const text = raw.trim();
    if (!text) return;

    this.onTranscript(text, isFinal);

    if (!this._active && this._containsWakeWord(text)) {
      this.activate(true);
      const cmd = this._extractCommand(text);
      if (cmd) {
        this._commandBuffer = cmd;
        this._lastCommandAt = Date.now();
      }
      return;
    }

    if (!this._active || !this._commandMode) return;

    this._armIdleTimer();

    if (this._containsWakeWord(text) && !this._extractCommand(text)) {
      this._setPhase('listening');
      return;
    }

    const piece = this._extractCommand(text) || this._normalize(text);
    if (!piece) return;

    if (isFinal) {
      this._commandBuffer = this._commandBuffer
        ? `${this._commandBuffer} ${piece}`.trim()
        : piece;
      this._lastCommandAt = Date.now();
      this._setPhase('listening');
      return;
    }

    this._setPhase('listening');
  }

  _maybeFinalizeCommand() {
    if (!this._active || !this._commandBuffer) return;
    const cmd = this._commandBuffer.trim();
    this._commandBuffer = '';
    this._commandMode = false;
    this._setPhase('thinking');
    Promise.resolve(this.onCommand(cmd)).finally(() => {
      if (this._active) this._armIdleTimer();
    });
  }

  _watchCommandCompletion() {
    setInterval(() => {
      if (!this._active || !this._commandMode || !this._commandBuffer) return;
      if (Date.now() - this._lastCommandAt > this.commandSilenceMs) {
        this._maybeFinalizeCommand();
      }
    }, 200);
  }

  start() {
    if (!this._supported) {
      this.onError(new Error('Speech recognition not supported. Use Chrome or Edge on desktop.'));
      return this;
    }
    if (this._listening) return this;

    this._recognition = new SpeechRecognition();
    this._recognition.continuous = true;
    this._recognition.interimResults = true;
    this._recognition.lang = this.lang;

    this._recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        this._handleTranscript(result[0].transcript, result.isFinal);
      }
    };

    this._recognition.onerror = (event) => {
      if (event.error === 'no-speech' || event.error === 'aborted') return;
      this.onError(new Error(event.error));
    };

    this._recognition.onend = () => {
      this._listening = false;
      if (this._shouldRestart) {
        try {
          this._recognition.start();
          this._listening = true;
        } catch {
          /* ignore */
        }
      }
    };

    this._shouldRestart = true;
    this._watchCommandCompletion();
    this._setPhase('dormant');

    try {
      this._recognition.start();
      this._listening = true;
    } catch (err) {
      this.onError(err);
    }

    return this;
  }

  stop() {
    this._shouldRestart = false;
    this._clearIdleTimer();
    if (this._recognition) {
      try {
        this._recognition.stop();
      } catch {
        /* ignore */
      }
    }
    this._listening = false;
    this.deactivate();
    return this;
  }

  setSpeaking(level = 0.5) {
    if (!this._active) return this;
    this._setPhase('speaking');
    this._armIdleTimer();
    return level;
  }

  finishSpeaking() {
    if (!this._active) return;
    this._setPhase('idle');
    this._commandMode = true;
    this._setPhase('listening');
    this._armIdleTimer();
  }
}

export default JarvisWakeAssistant;
