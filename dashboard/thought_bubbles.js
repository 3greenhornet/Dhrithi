/**
 * Dhriti Thought Bubbles (D-092 / L-2 / L-8)
 * Screensaver floating thought bubbles inspired by sketch dialogue & cloud forms.
 * Surfaces organically from the bottom, rises gently, and dissolves.
 * No buttons, no counters, no manipulative engagement affordance.
 * Modes: AUTO (decompression / evening window) | ON (continuous) | OFF.
 */

(() => {
  "use strict";

  const KEY = "dhriti.bubbles.mode"; // 'auto' | 'on' | 'off'
  const CFG = {
    maxOnScreen: 3,
    spawnEveryMs: [8000, 16000],
    riseSeconds: [14, 22]
  };

  const SHAPES = ["shape-cloud", "shape-oval", "shape-rect"];
  const SIZES = ["size-1", "size-2", "size-3"];

  const DEFAULT_PROMPTS = [
    "Look out at the far horizon and rest your gaze — 2m",
    "Deep spine stretch & shoulder release",
    "Drink a cool glass of water in silence",
    "Close your eyes and breathe slowly for 60 seconds",
    "Notice the quiet space around you before your next thought",
    "Gentle wrist and neck rotations",
    "Step outside to feel the natural breeze and daylight"
  ];

  let mode = localStorage.getItem(KEY) || "auto";
  let decompressionActive = false;
  let feed = [...DEFAULT_PROMPTS];
  let spawnTimer = null;

  // Layer attached to body
  let layer = document.getElementById("thought-bubble-layer");
  if (!layer) {
    layer = document.createElement("div");
    layer.id = "thought-bubble-layer";
    document.body.appendChild(layer);
  }

  // Fetch life alternatives from bridge daemon
  async function refreshFeed() {
    try {
      const resp = await fetch("/status");
      if (resp.ok) {
        const j = await resp.json();
        const alts = j.life_alternatives || j.alternatives || [];
        if (alts.length > 0) {
          feed = alts.map(a => a.label || a.text || a);
          return;
        }
      }
    } catch (e) {
      // Offline fallback
    }
    if (!feed || feed.length === 0) {
      feed = [...DEFAULT_PROMPTS];
    }
  }

  async function pollDecompressionState() {
    try {
      const resp = await fetch("/status");
      if (resp.ok) {
        const j = await resp.json();
        decompressionActive = !!(j.decompression && j.decompression.active);
      }
    } catch (e) {
      decompressionActive = false;
    }
    updateLoopState();
  }

  function shouldRun() {
    if (mode === "on") return true;
    if (mode === "auto") {
      // Run if decompression active, or if mode is auto and evening hours
      const hour = new Date().getHours();
      return decompressionActive || (hour >= 18 || hour < 6);
    }
    return false;
  }

  function spawnBubble() {
    if (!shouldRun() || !feed.length) return;
    if (layer.children.length >= CFG.maxOnScreen) return;

    const text = feed[Math.floor(Math.random() * feed.length)];
    const shape = SHAPES[Math.floor(Math.random() * SHAPES.length)];
    const size = SIZES[Math.floor(Math.random() * SIZES.length)];

    const bubble = document.createElement("div");
    bubble.className = `thought-bubble ${shape} ${size}`;
    bubble.textContent = text;

    // Random placement across viewport
    const leftVw = 8 + Math.random() * 70;
    const topVh = 72 + Math.random() * 18;
    const durSec = CFG.riseSeconds[0] + Math.random() * (CFG.riseSeconds[1] - CFG.riseSeconds[0]);
    const driftVw = (Math.random() * 8 - 4).toFixed(1);

    bubble.style.left = `${leftVw}vw`;
    bubble.style.top = `${topVh}vh`;
    bubble.style.setProperty("--rise-dur", `${durSec}s`);
    bubble.style.setProperty("--drift-x", `${driftVw}vw`);

    layer.appendChild(bubble);

    // Trigger rise animation on next frame
    requestAnimationFrame(() => {
      bubble.classList.add("rising");
    });

    bubble.addEventListener("animationend", () => {
      bubble.remove();
    }, { once: true });
  }

  function scheduleNext() {
    clearTimeout(spawnTimer);
    if (!shouldRun()) return;
    spawnBubble();
    const delay = CFG.spawnEveryMs[0] + Math.random() * (CFG.spawnEveryMs[1] - CFG.spawnEveryMs[0]);
    spawnTimer = setTimeout(scheduleNext, delay);
  }

  function updateLoopState() {
    if (shouldRun()) {
      if (!spawnTimer) scheduleNext();
    } else {
      clearTimeout(spawnTimer);
      spawnTimer = null;
      if (layer) layer.innerHTML = "";
    }
  }

  function updateToggleUI() {
    const labelSpan = document.getElementById("bubbles-mode-label");
    if (labelSpan) {
      labelSpan.textContent = mode.toUpperCase();
    }
  }

  function wireToggle() {
    const btn = document.getElementById("btn-toggle-thought-bubbles");
    if (btn) {
      btn.addEventListener("click", () => {
        if (mode === "auto") mode = "on";
        else if (mode === "on") mode = "off";
        else mode = "auto";

        localStorage.setItem(KEY, mode);
        updateToggleUI();
        updateLoopState();
        if (window.DhritiAudio) window.DhritiAudio.playBell();
      });
    }
    updateToggleUI();
  }

  // --- Initialization ---
  function init() {
    wireToggle();
    refreshFeed();
    pollDecompressionState();
    setInterval(pollDecompressionState, 25000);
    setInterval(refreshFeed, 120000);
    updateLoopState();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
