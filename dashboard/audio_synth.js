/**
 * Dhriti Audio Synthesizer (Web Audio API)
 * Pure procedural audio synthesis — zero sample files, zero dependencies.
 *
 * Implements:
 * 1. Physical metallic chimes for string cloth interaction with authentic country-tuned timbres
 *    (China, Japan, Vietnam, Kazakhstan, Russia, France, India, UK, Norway, Italy, USA, Brazil, Iran)
 *    using harmonic partials, droop exponential ramp, high-shelf coloration, and bandpass noise bursts.
 * 2. Procedural Pomodoro alarm catalog (Singing Bowl, Wind Chimes, Bicycle Bell, Temple Bell, Digital Beep, Klaxon, etc.)
 * 3. Continuous Focus Ambient Noise Generator (Brown, Pink, White noise)
 */
(() => {
  "use strict";

  // --- Country Chimes Acoustic Profiles ---
  const COUNTRY_CHIMES = {
    china: {
      name: "China",
      freqs: [261.63, 293.66, 329.63, 392.0, 440.0, 523.25, 587.33, 659.25],
      partials: [
        { ratio: 1.0, gain: 0.62 },
        { ratio: 1.5, gain: 0.12 },
        { ratio: 2.0, gain: 0.20 },
        { ratio: 2.76, gain: 0.22 },
        { ratio: 4.07, gain: 0.06 }
      ],
      duration: 1.45,
      attack: 0.018,
      peak: 0.20,
      droop: 0.988,
      noiseDur: 0.05,
      noiseGain: 0.06,
      noiseQ: 2.5,
      noiseMul: 1.6,
      shelfHz: 1200,
      shelfGain: 1,
      minIntervalMs: 70
    },
    japan: {
      name: "Japan",
      freqs: [659.25, 783.99, 880.0, 987.77, 1046.5, 1174.7, 1318.5, 1568.0],
      partials: [
        { ratio: 1.0, gain: 0.45 },
        { ratio: 2.0, gain: 0.28 },
        { ratio: 3.01, gain: 0.18 },
        { ratio: 4.2, gain: 0.10 },
        { ratio: 6.7, gain: 0.05 }
      ],
      duration: 0.85,
      attack: 0.004,
      peak: 0.16,
      droop: 0.996,
      noiseDur: 0.025,
      noiseGain: 0.12,
      noiseQ: 8,
      noiseMul: 3.4,
      shelfHz: 2800,
      shelfGain: 6,
      minIntervalMs: 42
    },
    vietnam: {
      name: "Vietnam",
      freqs: [349.23, 392.0, 440.0, 523.25, 587.33, 659.25, 698.46, 784.0],
      partials: [
        { ratio: 1.0, gain: 0.58 },
        { ratio: 2.0, gain: 0.22 },
        { ratio: 2.4, gain: 0.16 },
        { ratio: 3.6, gain: 0.10 },
        { ratio: 5.0, gain: 0.05 }
      ],
      duration: 1.15,
      attack: 0.01,
      peak: 0.18,
      droop: 0.991,
      noiseDur: 0.035,
      noiseGain: 0.08,
      noiseQ: 4,
      noiseMul: 2.1,
      shelfHz: 1600,
      shelfGain: 3,
      minIntervalMs: 55
    },
    india: {
      name: "India",
      freqs: [220.0, 261.63, 311.13, 349.23, 392.0, 466.16, 523.25, 622.25],
      partials: [
        { ratio: 1.0, gain: 0.60 },
        { ratio: 1.5, gain: 0.18 },
        { ratio: 2.0, gain: 0.20 },
        { ratio: 2.85, gain: 0.14 },
        { ratio: 4.1, gain: 0.06 }
      ],
      duration: 1.35,
      attack: 0.014,
      peak: 0.20,
      droop: 0.989,
      noiseDur: 0.045,
      noiseGain: 0.07,
      noiseQ: 3.2,
      noiseMul: 1.8,
      shelfHz: 1400,
      shelfGain: 2,
      minIntervalMs: 62
    },
    kazakhstan: {
      name: "Kazakhstan",
      freqs: [311.13, 369.99, 415.3, 466.16, 554.37, 622.25, 739.99, 830.61],
      partials: [
        { ratio: 1.0, gain: 0.50 },
        { ratio: 1.48, gain: 0.22 },
        { ratio: 2.15, gain: 0.20 },
        { ratio: 3.3, gain: 0.12 },
        { ratio: 4.8, gain: 0.06 }
      ],
      duration: 1.05,
      attack: 0.006,
      peak: 0.17,
      droop: 0.994,
      noiseDur: 0.03,
      noiseGain: 0.10,
      noiseQ: 5.5,
      noiseMul: 2.6,
      shelfHz: 2000,
      shelfGain: 4,
      minIntervalMs: 48
    },
    russia: {
      name: "Russia",
      freqs: [196.0, 246.94, 293.66, 349.23, 392.0, 466.16, 523.25, 587.33],
      partials: [
        { ratio: 1.0, gain: 0.65 },
        { ratio: 2.0, gain: 0.25 },
        { ratio: 3.01, gain: 0.14 },
        { ratio: 4.2, gain: 0.08 },
        { ratio: 5.4, gain: 0.04 }
      ],
      duration: 1.60,
      attack: 0.02,
      peak: 0.22,
      droop: 0.986,
      noiseDur: 0.055,
      noiseGain: 0.05,
      noiseQ: 2.2,
      noiseMul: 1.4,
      shelfHz: 900,
      shelfGain: 0.5,
      minIntervalMs: 75
    },
    france: {
      name: "France",
      freqs: [392.0, 440.0, 523.25, 587.33, 659.25, 783.99, 880.0, 987.77],
      partials: [
        { ratio: 1.0, gain: 0.48 },
        { ratio: 2.0, gain: 0.26 },
        { ratio: 3.0, gain: 0.16 },
        { ratio: 4.5, gain: 0.10 },
        { ratio: 6.0, gain: 0.05 }
      ],
      duration: 1.00,
      attack: 0.006,
      peak: 0.17,
      droop: 0.993,
      noiseDur: 0.028,
      noiseGain: 0.10,
      noiseQ: 6,
      noiseMul: 2.8,
      shelfHz: 2200,
      shelfGain: 4.5,
      minIntervalMs: 48
    },
    uk: {
      name: "United Kingdom",
      freqs: [293.66, 329.63, 392.0, 440.0, 493.88, 587.33, 659.25, 783.99],
      partials: [
        { ratio: 1.0, gain: 0.55 },
        { ratio: 2.0, gain: 0.24 },
        { ratio: 2.5, gain: 0.14 },
        { ratio: 3.8, gain: 0.10 },
        { ratio: 5.2, gain: 0.05 }
      ],
      duration: 1.20,
      attack: 0.01,
      peak: 0.18,
      droop: 0.991,
      noiseDur: 0.032,
      noiseGain: 0.08,
      noiseQ: 4.5,
      noiseMul: 2.2,
      shelfHz: 1700,
      shelfGain: 3,
      minIntervalMs: 55
    },
    norway: {
      name: "Norway",
      freqs: [523.25, 587.33, 659.25, 783.99, 880.0, 987.77, 1174.7, 1318.5],
      partials: [
        { ratio: 1.0, gain: 0.42 },
        { ratio: 2.0, gain: 0.30 },
        { ratio: 3.2, gain: 0.16 },
        { ratio: 5.0, gain: 0.10 },
        { ratio: 7.1, gain: 0.05 }
      ],
      duration: 0.90,
      attack: 0.004,
      peak: 0.15,
      droop: 0.995,
      noiseDur: 0.022,
      noiseGain: 0.11,
      noiseQ: 7.5,
      noiseMul: 3.2,
      shelfHz: 2600,
      shelfGain: 5.5,
      minIntervalMs: 44
    },
    italy: {
      name: "Italy",
      freqs: [246.94, 293.66, 349.23, 392.0, 466.16, 523.25, 587.33, 698.46],
      partials: [
        { ratio: 1.0, gain: 0.58 },
        { ratio: 2.0, gain: 0.24 },
        { ratio: 2.7, gain: 0.15 },
        { ratio: 3.9, gain: 0.10 },
        { ratio: 5.1, gain: 0.05 }
      ],
      duration: 1.40,
      attack: 0.016,
      peak: 0.20,
      droop: 0.988,
      noiseDur: 0.04,
      noiseGain: 0.065,
      noiseQ: 3,
      noiseMul: 1.7,
      shelfHz: 1300,
      shelfGain: 1.5,
      minIntervalMs: 65
    },
    usa: {
      name: "USA",
      freqs: [392.0, 440.0, 523.25, 587.33, 659.25, 783.99, 880.0, 987.77],
      partials: [
        { ratio: 1.0, gain: 0.50 },
        { ratio: 2.0, gain: 0.28 },
        { ratio: 3.0, gain: 0.14 },
        { ratio: 4.2, gain: 0.08 },
        { ratio: 6.0, gain: 0.04 }
      ],
      duration: 1.05,
      attack: 0.008,
      peak: 0.17,
      droop: 0.992,
      noiseDur: 0.028,
      noiseGain: 0.09,
      noiseQ: 5.5,
      noiseMul: 2.4,
      shelfHz: 2200,
      shelfGain: 4,
      minIntervalMs: 50
    },
    brazil: {
      name: "Brazil",
      freqs: [293.66, 349.23, 392.0, 466.16, 523.25, 587.33, 698.46, 783.99],
      partials: [
        { ratio: 1.0, gain: 0.55 },
        { ratio: 2.0, gain: 0.26 },
        { ratio: 2.8, gain: 0.14 },
        { ratio: 3.7, gain: 0.09 },
        { ratio: 5.0, gain: 0.05 }
      ],
      duration: 1.25,
      attack: 0.012,
      peak: 0.19,
      droop: 0.989,
      noiseDur: 0.036,
      noiseGain: 0.075,
      noiseQ: 3.5,
      noiseMul: 1.9,
      shelfHz: 1600,
      shelfGain: 2.5,
      minIntervalMs: 58
    },
    iran: {
      name: "Iran",
      freqs: [220.0, 261.63, 311.13, 349.23, 415.3, 466.16, 523.25, 622.25],
      partials: [
        { ratio: 1.0, gain: 0.60 },
        { ratio: 1.5, gain: 0.14 },
        { ratio: 2.0, gain: 0.22 },
        { ratio: 2.9, gain: 0.12 },
        { ratio: 4.5, gain: 0.06 }
      ],
      duration: 1.50,
      attack: 0.02,
      peak: 0.20,
      droop: 0.987,
      noiseDur: 0.045,
      noiseGain: 0.055,
      noiseQ: 2.8,
      noiseMul: 1.5,
      shelfHz: 1100,
      shelfGain: 1.2,
      minIntervalMs: 68
    }
  };

  // --- StringChimes Physical Bell Synthesizer (Niyam Vora Model) ---
  class StringChimes {
    constructor() {
      this.ctx = null;
      this.master = null;
      this.shelf = null;
      this.enabled = true;
      this.volume = 0.28;
      this.countryId = "china";
      this.profile = COUNTRY_CHIMES.china;
      this.lastStrikeAt = 0;
      this.activeVoices = 0;
      this.maxVoices = 12;
      this.lastParticleId = -1;
      this.prevX = 0;
      this.prevY = 0;
    }

    setCountry(id) {
      if (COUNTRY_CHIMES[id]) {
        this.countryId = id;
        this.profile = COUNTRY_CHIMES[id];
        this.lastParticleId = -1;
        if (this.shelf) {
          this.shelf.frequency.value = this.profile.shelfHz;
          this.shelf.gain.value = this.profile.shelfGain;
        }
      }
    }

    warm() {
      if (this.ctx) return true;
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return false;
      this.ctx = new AC();
      this.master = this.ctx.createGain();
      this.master.gain.value = this.volume;

      this.shelf = this.ctx.createBiquadFilter();
      this.shelf.type = "highshelf";
      this.shelf.frequency.value = this.profile.shelfHz;
      this.shelf.gain.value = this.profile.shelfGain;

      this.master.connect(this.shelf);
      this.shelf.connect(this.ctx.destination);

      // Prime output with 1-sample silent buffer
      try {
        const prime = this.ctx.createBufferSource();
        prime.buffer = this.ctx.createBuffer(1, 1, this.ctx.sampleRate);
        prime.connect(this.ctx.destination);
        prime.start(0);
      } catch (_) {}
      return true;
    }

    async ensure() {
      if (!this.warm()) return false;
      if (this.ctx.state === "suspended") {
        try {
          await this.ctx.resume();
        } catch (_) {
          return false;
        }
      }
      return this.ctx.state === "running";
    }

    setVolume(v) {
      this.volume = Math.max(0, Math.min(1, v));
      if (this.master) this.master.gain.value = this.volume;
    }

    async strike(opts = {}) {
      if (!this.enabled) return;
      const ok = await this.ensure();
      if (!ok || !this.ctx) return;

      const profile = this.profile;
      const now = performance.now();
      const force = !!opts.force;
      if (!force && now - this.lastStrikeAt < profile.minIntervalMs) return;
      if (this.activeVoices >= this.maxVoices) return;

      const particle = opts.particle;
      if (particle && particle.id === this.lastParticleId && !force) return;

      const dx = (opts.x ?? 0) - this.prevX;
      const dy = (opts.y ?? 0) - this.prevY;
      const speed = Math.hypot(dx, dy);
      this.prevX = opts.x ?? this.prevX;
      this.prevY = opts.y ?? this.prevY;

      let intensity = opts.intensity;
      if (intensity == null) {
        intensity = Math.min(1, 0.25 + speed / 40);
      }
      if (!force && intensity < 0.2 && speed < 1.5) return;

      this.lastStrikeAt = now;
      if (particle) this.lastParticleId = particle.id;

      const freqs = profile.freqs;
      const pitchT =
        particle && opts.gridW > 1
          ? (particle.id % opts.gridW) / (opts.gridW - 1)
          : Math.random();
      const idx = Math.min(
        freqs.length - 1,
        Math.max(0, Math.round(pitchT * (freqs.length - 1) + (Math.random() - 0.5)))
      );
      const freq = freqs[idx] * (0.985 + Math.random() * 0.03);

      this.playBellVoice(freq, intensity, profile);
    }

    playBellVoice(freq, intensity, profile) {
      const ctx = this.ctx;
      const t = ctx.currentTime;
      const duration = profile.duration * (0.75 + intensity * 0.5);

      const voice = ctx.createGain();
      const peak = profile.peak * (0.55 + intensity * 0.7);
      voice.gain.setValueAtTime(0.0001, t);
      voice.gain.exponentialRampToValueAtTime(Math.max(0.0002, peak), t + profile.attack);
      voice.gain.exponentialRampToValueAtTime(0.0001, t + duration);
      voice.connect(this.master);

      this.activeVoices += 1;
      window.setTimeout(() => {
        this.activeVoices = Math.max(0, this.activeVoices - 1);
      }, (duration + 0.05) * 1000);

      // Partials with droop
      for (const { ratio, gain } of profile.partials) {
        const osc = ctx.createOscillator();
        const g = ctx.createGain();
        osc.type = "sine";
        const f0 = freq * ratio;
        osc.frequency.setValueAtTime(f0, t);
        osc.frequency.exponentialRampToValueAtTime(
          Math.max(20, f0 * profile.droop),
          t + duration
        );
        g.gain.value = gain;
        osc.connect(g);
        g.connect(voice);
        osc.start(t);
        osc.stop(t + duration + 0.02);
      }

      // Metallic impact noise burst
      const noiseDur = profile.noiseDur;
      const buffer = ctx.createBuffer(
        1,
        Math.max(1, Math.floor(ctx.sampleRate * noiseDur)),
        ctx.sampleRate
      );
      const data = buffer.getChannelData(0);
      for (let i = 0; i < data.length; i++) {
        data[i] = (Math.random() * 2 - 1) * (1 - i / data.length);
      }
      const noise = ctx.createBufferSource();
      noise.buffer = buffer;
      const noiseFilter = ctx.createBiquadFilter();
      noiseFilter.type = "bandpass";
      noiseFilter.frequency.value = freq * profile.noiseMul;
      noiseFilter.Q.value = profile.noiseQ;
      const noiseGain = ctx.createGain();
      noiseGain.gain.setValueAtTime(
        Math.max(0.0001, profile.noiseGain * intensity),
        t
      );
      noiseGain.gain.exponentialRampToValueAtTime(0.0001, t + noiseDur);
      noise.connect(noiseFilter);
      noiseFilter.connect(noiseGain);
      noiseGain.connect(voice);
      noise.start(t);
      noise.stop(t + noiseDur + 0.01);
    }
  }

  const stringChimes = new StringChimes();

  // --- Procedural Alarms & Noise Generator ---
  let sharedCtx = null;
  let noiseNode = null;
  let noiseGain = null;

  function getSharedCtx() {
    if (!sharedCtx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) sharedCtx = new AC();
    }
    if (sharedCtx && sharedCtx.state === "suspended") {
      sharedCtx.resume();
    }
    return sharedCtx;
  }

  function playFlipClick(velocity = 0.5) {
    const ctx = getSharedCtx();
    if (!ctx) return;
    const t = ctx.currentTime;
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(800, t);
    osc.frequency.exponentialRampToValueAtTime(220, t + 0.035);
    g.gain.setValueAtTime(0.18 * velocity, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.035);
    osc.connect(g);
    g.connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.04);
  }

  function playBell(fundamental = 440, duration = 3.5) {
    const ctx = getSharedCtx();
    if (!ctx) return;
    const t = ctx.currentTime;
    const modalRatios = [
      { r: 1.0, g: 0.6, d: duration },
      { r: 2.76, g: 0.28, d: duration * 0.7 },
      { r: 5.4, g: 0.18, d: duration * 0.5 },
      { r: 8.9, g: 0.09, d: duration * 0.35 }
    ];
    modalRatios.forEach(m => {
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(fundamental * m.r, t);
      g.gain.setValueAtTime(0.001, t);
      g.gain.linearRampToValueAtTime(m.g * 0.4, t + 0.04);
      g.gain.exponentialRampToValueAtTime(0.0001, t + m.d);
      osc.connect(g);
      g.connect(ctx.destination);
      osc.start(t);
      osc.stop(t + m.d + 0.05);
    });
  }

  function playProceduralAlarm(name = "singing_bowl") {
    switch (name) {
      case "singing_bowl":
        playBell(349.23, 4.0); // F4 Tibetan bowl
        break;
      case "wind_chimes":
        stringChimes.strike({ x: 100, y: 100, intensity: 0.9, force: true });
        setTimeout(() => stringChimes.strike({ x: 200, y: 120, intensity: 0.8, force: true }), 120);
        setTimeout(() => stringChimes.strike({ x: 300, y: 140, intensity: 0.7, force: true }), 240);
        break;
      case "bicycle_bell":
        playBicycleBell();
        break;
      case "temple_bell":
        playBell(196.0, 5.0); // G3 Deep bronze temple bell
        break;
      case "digital_beep":
        playDigitalBeep();
        break;
      case "klaxon":
        playKlaxon();
        break;
      case "toy_honk":
        playToyHonk();
        break;
      case "clown_horn":
        playClownHorn();
        break;
      case "drum_crash":
        playDrumCrash();
        break;
      default:
        playBell(440, 3.0);
    }
  }

  function playBicycleBell() {
    const ctx = getSharedCtx();
    if (!ctx) return;
    const ring = (delay) => {
      const t = ctx.currentTime + delay;
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const g = ctx.createGain();
      osc1.type = "sine";
      osc2.type = "sine";
      osc1.frequency.setValueAtTime(2093, t); // C7
      osc2.frequency.setValueAtTime(2500, t);
      g.gain.setValueAtTime(0.25, t);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.28);
      osc1.connect(g);
      osc2.connect(g);
      g.connect(ctx.destination);
      osc1.start(t);
      osc2.start(t);
      osc1.stop(t + 0.3);
      osc2.stop(t + 0.3);
    };
    ring(0.0);
    ring(0.08);
  }

  function playDigitalBeep() {
    const ctx = getSharedCtx();
    if (!ctx) return;
    const beep = (delay, freq) => {
      const t = ctx.currentTime + delay;
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = "square";
      osc.frequency.setValueAtTime(freq, t);
      g.gain.setValueAtTime(0.12, t);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.08);
      osc.connect(g);
      g.connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.09);
    };
    beep(0.0, 1046.5);
    beep(0.1, 1318.5);
  }

  function playKlaxon() {
    const ctx = getSharedCtx();
    if (!ctx) return;
    const t = ctx.currentTime;
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(440, t);
    osc.frequency.linearRampToValueAtTime(320, t + 0.35);
    g.gain.setValueAtTime(0.2, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.38);
    osc.connect(g);
    g.connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.4);
  }

  function playToyHonk() {
    const ctx = getSharedCtx();
    if (!ctx) return;
    const t = ctx.currentTime;
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(350, t);
    osc.frequency.exponentialRampToValueAtTime(450, t + 0.12);
    g.gain.setValueAtTime(0.25, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.22);
    osc.connect(g);
    g.connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.25);
  }

  function playClownHorn() {
    const ctx = getSharedCtx();
    if (!ctx) return;
    const t = ctx.currentTime;
    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const g = ctx.createGain();
    osc1.type = "sawtooth";
    osc2.type = "square";
    osc1.frequency.setValueAtTime(293.66, t);
    osc2.frequency.setValueAtTime(369.99, t);
    g.gain.setValueAtTime(0.22, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.28);
    osc1.connect(g);
    osc2.connect(g);
    g.connect(ctx.destination);
    osc1.start(t);
    osc2.start(t);
    osc1.stop(t + 0.3);
    osc2.stop(t + 0.3);
  }

  function playDrumCrash() {
    const ctx = getSharedCtx();
    if (!ctx) return;
    const t = ctx.currentTime;
    const bufferSize = ctx.sampleRate * 0.6;
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (ctx.sampleRate * 0.15));
    }
    const noise = ctx.createBufferSource();
    noise.buffer = buffer;
    const filter = ctx.createBiquadFilter();
    filter.type = "highpass";
    filter.frequency.setValueAtTime(1200, t);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.35, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.6);
    noise.connect(filter);
    filter.connect(g);
    g.connect(ctx.destination);
    noise.start(t);
    noise.stop(t + 0.62);
  }

  // --- Noise Generator (Brown / Pink / White) ---
  function startNoise(type = "brown", volume = 0.3) {
    stopNoise();
    const ctx = getSharedCtx();
    if (!ctx) return;
    const bufferSize = ctx.sampleRate * 4;
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);

    if (type === "white") {
      for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;
    } else if (type === "pink") {
      let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1;
        b0 = 0.99886 * b0 + white * 0.0555179;
        b1 = 0.99332 * b1 + white * 0.0750759;
        b2 = 0.96900 * b2 + white * 0.1538520;
        b3 = 0.86650 * b3 + white * 0.3104856;
        b4 = 0.55000 * b4 + white * 0.5329522;
        b5 = -0.7616 * b5 - white * 0.0168980;
        data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11;
        b6 = white * 0.115926;
      }
    } else {
      // Brown noise
      let lastOut = 0.0;
      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1;
        data[i] = (lastOut + (0.02 * white)) / 1.02;
        lastOut = data[i];
        data[i] *= 3.5;
      }
    }

    noiseNode = ctx.createBufferSource();
    noiseNode.buffer = buffer;
    noiseNode.loop = true;
    noiseGain = ctx.createGain();
    noiseGain.gain.setValueAtTime(volume, ctx.currentTime);
    noiseNode.connect(noiseGain);
    noiseGain.connect(ctx.destination);
    noiseNode.start(0);
  }

  function stopNoise() {
    if (noiseNode) {
      try { noiseNode.stop(); } catch (_) {}
      noiseNode = null;
    }
  }

  function setNoiseVolume(vol) {
    if (noiseGain && sharedCtx) {
      noiseGain.gain.setValueAtTime(Math.max(0, Math.min(1, vol)), sharedCtx.currentTime);
    }
  }

  // --- Eager Context Warming on First User Gesture ---
  const warmAudio = () => {
    stringChimes.warm();
    stringChimes.ensure().then(ok => {
      if (ok) {
        window.removeEventListener("pointerdown", warmAudio, true);
        window.removeEventListener("touchstart", warmAudio, true);
        window.removeEventListener("keydown", warmAudio, true);
      }
    });
  };
  window.addEventListener("pointerdown", warmAudio, { capture: true });
  window.addEventListener("touchstart", warmAudio, { capture: true, passive: true });
  window.addEventListener("keydown", warmAudio, { capture: true });

  // Expose to window.DhritiAudio
  window.DhritiAudio = {
    chimes: stringChimes,
    COUNTRY_CHIMES,
    playChime: (noteIdx, vel) => stringChimes.strike({ x: noteIdx * 40, y: 100, intensity: vel, force: true }),
    playFlipClick,
    playBell,
    playProceduralAlarm,
    startNoise,
    stopNoise,
    setNoiseVolume
  };

})();
