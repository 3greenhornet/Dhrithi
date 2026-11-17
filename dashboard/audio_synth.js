/**
 * Dhriti Audio Synthesizer (Web Audio API)
 * Pure procedural audio synthesis — zero sample files, zero dependencies.
 * Synthesizes physical wind chimes, card sweep clicks, and meditative completion bells.
 */
(() => {
  "use strict";

  let ctx = null;
  let masterGain = null;
  let audioEnabled = true;

  function initAudio() {
    if (!ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        ctx = new AudioCtx();
        masterGain = ctx.createGain();
        masterGain.gain.setValueAtTime(0.5, ctx.currentTime);
        masterGain.connect(ctx.destination);
      }
    }
    if (ctx && ctx.state === "suspended") {
      ctx.resume();
    }
  }

  // Expanded Pentatonic Japanese Akebono / Pythagorean chime scale frequencies (Hz) across 2.5 octaves
  const CHIME_FREQS = [
    196.00, 220.00, 246.94, 261.63, 293.66, 329.63, 392.00, 440.00, 493.88,
    523.25, 587.33, 659.25, 783.99, 880.00, 987.77, 1046.50, 1174.66, 1318.51
  ];

  let lastChimeTime = 0;
  const MIN_CHIME_INTERVAL = 0.045; // 45ms throttle prevents audio buffer clipping

  /**
   * Resonant physical wind chime note
   * @param {number} noteIdx - Index into chime scale or explicit frequency
   * @param {number} velocity - Impact intensity [0.1, 1.0]
   */
  function playChime(noteIdx = 0, velocity = 0.5) {
    if (!audioEnabled) return;
    initAudio();
    if (!ctx) return;

    const now = ctx.currentTime;
    if (now - lastChimeTime < MIN_CHIME_INTERVAL) return;
    lastChimeTime = now;

    const baseFreq = typeof noteIdx === "number" && noteIdx < CHIME_FREQS.length
      ? CHIME_FREQS[Math.abs(noteIdx) % CHIME_FREQS.length]
      : (typeof noteIdx === "number" ? noteIdx : 440);

    const vel = Math.max(0.1, Math.min(1.0, velocity));

    // Wind chime harmonic partials (modal ratios for tubular bells: 1.0, 2.76, 5.40)
    const partials = [
      { mult: 1.00, gain: 0.50 * vel, decay: 2.0 },
      { mult: 2.76, gain: 0.28 * vel, decay: 1.3 },
      { mult: 5.40, gain: 0.12 * vel, decay: 0.8 },
    ];

    partials.forEach(({ mult, gain, decay }) => {
      const osc = ctx.createOscillator();
      const g = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(baseFreq * mult, now);

      g.gain.setValueAtTime(gain * 0.35, now);
      g.gain.exponentialRampToValueAtTime(0.0001, now + decay);

      osc.connect(g);
      g.connect(masterGain);

      osc.start(now);
      osc.stop(now + decay);
    });
  }

  /**
   * Tactile Solitaire / card sweep flip click
   * @param {number} pitchMult - Multiplier for wave ripple effect
   */
  function playCardFlip(pitchMult = 1.0) {
    if (!audioEnabled) return;
    initAudio();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const g = ctx.createGain();

    osc.type = "triangle";
    osc.frequency.setValueAtTime(140 * pitchMult, now);
    osc.frequency.exponentialRampToValueAtTime(40, now + 0.04);

    g.gain.setValueAtTime(0.15, now);
    g.gain.exponentialRampToValueAtTime(0.001, now + 0.04);

    osc.connect(g);
    g.connect(masterGain);

    osc.start(now);
    osc.stop(now + 0.045);
  }

  /**
   * Tibetan singing bowl / completion bell
   */
  function playCompletionBell() {
    if (!audioEnabled) return;
    initAudio();
    if (!ctx) return;

    const now = ctx.currentTime;
    const baseFreq = 220; // A3 deep bowl

    const partials = [
      { f: baseFreq, g: 0.5, d: 4.5 },
      { f: baseFreq * 2.77, g: 0.3, d: 3.5 },
      { f: baseFreq * 5.18, g: 0.15, d: 2.5 }
    ];

    partials.forEach(({ f, g: gain, d: decay }) => {
      const osc = ctx.createOscillator();
      const gn = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(f, now);

      gn.gain.setValueAtTime(gain * 0.6, now);
      gn.gain.exponentialRampToValueAtTime(0.0001, now + decay);

      osc.connect(gn);
      gn.connect(masterGain);

      osc.start(now);
      osc.stop(now + decay);
    });
  }

  function setVolume(v) {
    if (masterGain && ctx) {
      masterGain.gain.setValueAtTime(Math.max(0, Math.min(1, v)), ctx.currentTime);
    }
  }

  function setAudioEnabled(enabled) {
    audioEnabled = !!enabled;
  }

  window.DhritiAudio = {
    init: initAudio,
    playChime,
    playCardFlip,
    playCompletionBell,
    setVolume,
    setAudioEnabled
  };
})();

