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

  // ---- D-095: procedural alarm catalog (zero sample files) ----
  let alarmGain = null, noiseGain = null, noiseSrc = null;
  function _bus(kind) {
    initAudio(); if (!ctx) return null;
    if (kind === 'alarm') {
      if (!alarmGain) {
        alarmGain = ctx.createGain();
        alarmGain.gain.value = 0.8;
        alarmGain.connect(masterGain || ctx.destination);
      }
      return alarmGain;
    }
    if (kind === 'noise') {
      if (!noiseGain) {
        noiseGain = ctx.createGain();
        noiseGain.gain.value = 0.25;
        noiseGain.connect(masterGain || ctx.destination);
      }
      return noiseGain;
    }
    return masterGain || ctx.destination;
  }

  function _tone(bus, {type='sine', f=440, f2=null, t=0, d=0.3, g=0.4, filter=null}) {
    if (!ctx) return;
    const o = ctx.createOscillator(), gn = ctx.createGain();
    const now = ctx.currentTime + t;
    o.type = type;
    o.frequency.setValueAtTime(f, now);
    if (f2) o.frequency.exponentialRampToValueAtTime(f2, now + d);
    gn.gain.setValueAtTime(g, now);
    gn.gain.exponentialRampToValueAtTime(0.0001, now + d);
    let node = o;
    if (filter) {
      const fl = ctx.createBiquadFilter();
      fl.type = filter.type;
      fl.frequency.value = filter.f;
      fl.Q.value = filter.q || 1;
      o.connect(fl);
      node = fl;
    }
    node.connect(gn);
    gn.connect(bus);
    o.start(now);
    o.stop(now + d + 0.05);
  }

  function _noiseBurst(bus, {t=0, d=0.4, g=0.4, hp=3000}) {
    if (!ctx) return;
    const len = Math.floor(ctx.sampleRate * d);
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < len; i++) ch[i] = (Math.random() * 2 - 1) * (1 - i / len);
    const s = ctx.createBufferSource();
    s.buffer = buf;
    const fl = ctx.createBiquadFilter();
    fl.type = 'highpass';
    fl.frequency.value = hp;
    const gn = ctx.createGain();
    gn.gain.value = g;
    s.connect(fl);
    fl.connect(gn);
    gn.connect(bus);
    s.start(ctx.currentTime + t);
  }

  const ALARMS = {
    windChimes: { label: 'Wind Chimes', play(b){ [0,2,4,7,9].forEach((n,i)=>_tone(b, {f:CHIME_FREQS[n%CHIME_FREQS.length]*2, t:i*0.12, d:1.4, g:0.25})); } },
    singingBowl: { label: 'Singing Bowl', play(b){ [220,609,1139].forEach((f,i)=>_tone(b, {f, t:i*0.02, d:3.5, g:0.35-i*0.1})); } },
    bicycleBell: { label: 'Bicycle Bell', play(b){ [0, 0.18].forEach(t=>{ _tone(b,{f:2093, t, d:0.5, g:0.3}); _tone(b,{f:2637, t, d:0.4, g:0.2}); }); } },
    klaxon: { label: 'Klaxon', play(b){ [0, 0.35].forEach(t=>_tone(b, {type:'sawtooth', f:440, f2:330, t, d:0.32, g:0.3, filter:{type:'lowpass', f:1200}})); } },
    toyHonk: { label: 'Toy Honk', play(b){ _tone(b,{type:'square', f:310, f2:240, d:0.35, g:0.25, filter:{type:'bandpass', f:600, q:2}}); } },
    clownHorn: { label: 'Clown Horn', play(b){ _tone(b,{type:'sawtooth', f:380, f2:520, d:0.22, g:0.25, filter:{type:'bandpass', f:900, q:3}}); _tone(b,{type:'sawtooth', f:520, f2:300, t:0.22, d:0.3, g:0.25, filter:{type:'bandpass', f:900, q:3}}); } },
    drumCrash: { label: 'Drum Crash', play(b){ _noiseBurst(b,{d:0.9, g:0.4, hp:4000}); _tone(b,{f:180, f2:70, d:0.25, g:0.35}); } },
    templeBell: { label: 'Temple Bell', play(b){ [660,1320,1980].forEach((f,i)=>_tone(b,{f, d:2.2-i*0.5, g:0.3-i*0.08})); } },
    digitalBeep: { label: 'Digital Beep', play(b){ [0, 0.15, 0.3].forEach(t=>_tone(b,{type:'square', f:1200, t, d:0.09, g:0.2})); } }
  };

  function playAlarm(id) {
    const b = _bus('alarm');
    if (!b) return;
    (ALARMS[id] || ALARMS.windChimes).play(b);
  }

  function alarmCatalog() {
    return Object.entries(ALARMS).map(([id, a]) => ({ id, label: a.label }));
  }

  function setAlarmVolume(v) {
    const b = _bus('alarm');
    if (b) b.gain.setValueAtTime(Math.max(0, Math.min(1, v)), ctx.currentTime);
  }

  function setNoiseVolume(v) {
    const b = _bus('noise');
    if (b) b.gain.setValueAtTime(Math.max(0, Math.min(1, v)), ctx.currentTime);
  }

  function startNoise(type) {
    stopNoise();
    const b = _bus('noise');
    if (!b || type === 'off' || !ctx) return;
    const len = ctx.sampleRate * 2;
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const ch = buf.getChannelData(0);
    let last = 0, b0=0, b1=0, b2=0;
    for (let i = 0; i < len; i++) {
      const w = Math.random() * 2 - 1;
      if (type === 'white') ch[i] = w * 0.5;
      else if (type === 'brown') { last = (last + 0.02 * w) / 1.02; ch[i] = last * 3.5; }
      else {
        b0 = 0.997 * b0 + 0.029 * w;
        b1 = 0.985 * b1 + 0.032 * w;
        b2 = 0.950 * b2 + 0.048 * w;
        ch[i] = (b0 + b1 + b2 + w * 0.05) * 0.6;
      }
    }
    noiseSrc = ctx.createBufferSource();
    noiseSrc.buffer = buf;
    noiseSrc.loop = true;
    noiseSrc.connect(b);
    noiseSrc.start();
  }

  function stopNoise() {
    if (noiseSrc) {
      try { noiseSrc.stop(); } catch (e) {}
      noiseSrc = null;
    }
  }

  window.DhritiAudio = {
    init: initAudio,
    playChime,
    playCardFlip,
    playCompletionBell,
    setVolume,
    setAudioEnabled,
    playAlarm,
    alarmCatalog,
    setAlarmVolume,
    setNoiseVolume,
    startNoise,
    stopNoise
  };
})();

