/**
 * Dhriti Thought Bubbles (D-092 / L-2 / L-8)
 * Screensaver floating thought bubbles inspired by sketch dialogue & cloud forms.
 * Surfaces cold-declared offline alternatives organically from bottom, rises gently, and dissolves.
 * STRICTLY NO generic wellness quotes ("drink water", "step outside").
 * STRICTLY NO buttons, counters, or manipulative engagement affordances.
 *
 * MODES:
 *   - OFF (default outside decompression, zero intrusion)
 *   - AUTO (surfaces ONLY during active decompression stage)
 *   - ON (continuous preview across viewport)
 */

(() => {
  "use strict";

  const KEY = "dhriti.bubbles.mode"; // 'off' | 'auto' | 'on'
  const CFG = {
    maxOnScreen: 3,
    spawnEveryMs: [9000, 18000],
    riseSeconds: [14, 22]
  };

  const SHAPES = ["shape-cloud", "shape-oval", "shape-rect"];
  const SIZES = ["size-1", "size-2", "size-3"];

  // Strictly operator-declared offline life alternatives (L-8 / D-092)
  const DEFAULT_LIFE_ALTS = [
    "Back exercises — min 10m",
    "Walk around neighborhood — 15m",
    "Acoustic guitar practice — 20m",
    "Deep breathing & posture reset — 5m",
    "Read physical book chapter — 15m"
  ];

  // Default mode is strictly OFF unless explicitly enabled or saved by user
  let mode = localStorage.getItem(KEY) || "off";
  let decompressionActive = false;
  let feed = [...DEFAULT_LIFE_ALTS];
  let spawnTimer = null;

  // Single persistent thought layer attached to body
  let layer = document.getElementById("thought-bubble-layer");
  if (!layer) {
    layer = document.createElement("div");
    layer.id = "thought-bubble-layer";
    document.body.appendChild(layer);
  }

  /**
   * Refreshes alternative pool strictly from operator-declared sources.
   * Priority: window.DhritiState.lifeAlts -> localStorage -> /life/list -> /status -> DEFAULT_LIFE_ALTS
   */
  async function refreshFeed() {
    let gathered = [];

    // 1. Check window.DhritiState (app.js state)
    if (window.DhritiState && Array.isArray(window.DhritiState.lifeAlts) && window.DhritiState.lifeAlts.length > 0) {
      gathered = window.DhritiState.lifeAlts.map(a => typeof a === "string" ? a : (a.label || a.title || ""));
    }

    // 2. Check localStorage
    if (gathered.length === 0) {
      try {
        const stored = localStorage.getItem("dhriti_life_alts");
        if (stored) {
          const parsed = JSON.parse(stored);
          if (Array.isArray(parsed) && parsed.length > 0) {
            gathered = parsed.map(a => typeof a === "string" ? a : (a.label || a.title || ""));
          }
        }
      } catch (e) {
        // Fall through
      }
    }

    // 3. Check /life/list or /status endpoints from daemon bridge
    if (gathered.length === 0) {
      try {
        const resp = await fetch("/life/list");
        if (resp.ok) {
          const j = await resp.json();
          const items = j.items || [];
          if (items.length > 0) {
            gathered = items.map(a => typeof a === "string" ? a : (a.label || ""));
          }
        }
      } catch (e) {
        // Fall through
      }
    }

    // Filter valid non-empty strings
    gathered = gathered.map(s => String(s || "").trim()).filter(s => s.length > 0);

    if (gathered.length > 0) {
      feed = gathered;
    } else {
      feed = [...DEFAULT_LIFE_ALTS];
    }
  }

  async function pollDecompressionState() {
    try {
      const resp = await fetch("/decompression/status");
      if (resp.ok) {
        const j = await resp.json();
        decompressionActive = !!(j && (j.active || j.in_decompression));
      } else {
        const sResp = await fetch("/status");
        if (sResp.ok) {
          const sj = await sResp.json();
          decompressionActive = !!(sj.decompression && sj.decompression.active);
        }
      }
    } catch (e) {
      // Local fallback: inspect DhritiState if present
      if (window.DhritiState && typeof window.DhritiState.isDecompressionActive === "boolean") {
        decompressionActive = window.DhritiState.isDecompressionActive;
      } else {
        decompressionActive = false;
      }
    }
    updateLoopState();
  }

  function shouldRun() {
    // STRICTLY NEVER run inside the Dashboard Shell (Mode 2)
    if (document.body.classList.contains("mode-dashboard") ||
        document.body.classList.contains("in-dashboard")) {
      return false;
    }
    const shell = document.getElementById("app-shell");
    if (shell && shell.style.display !== "none") {
      return false;
    }

    if (mode === "off") return false;
    if (mode === "on") return true;
    if (mode === "auto") {
      // AUTO mode strictly runs ONLY when decompression stage is active
      return decompressionActive === true;
    }
    return false;
  }

  function spawnBubble(textOverride) {
    if (!textOverride && !shouldRun()) return;
    if (!feed.length && !textOverride) return;
    if (layer.children.length >= CFG.maxOnScreen && !textOverride) return;

    const text = textOverride || feed[Math.floor(Math.random() * feed.length)];
    const shape = SHAPES[Math.floor(Math.random() * SHAPES.length)];
    const size = SIZES[Math.floor(Math.random() * SIZES.length)];

    const bubble = document.createElement("div");
    bubble.className = `thought-bubble ${shape} ${size}`;
    bubble.textContent = text;

    // Random placement across viewport
    const leftVw = 10 + Math.random() * 66;
    const topVh = 74 + Math.random() * 16;
    const durSec = CFG.riseSeconds[0] + Math.random() * (CFG.riseSeconds[1] - CFG.riseSeconds[0]);
    const driftVw = (Math.random() * 8 - 4).toFixed(1);

    bubble.style.left = `${leftVw}vw`;
    bubble.style.top = `${topVh}vh`;
    bubble.style.setProperty("--rise-dur", `${durSec}s`);
    bubble.style.setProperty("--drift-x", `${driftVw}vw`);

    layer.appendChild(bubble);

    // Trigger rise animation on next animation frame
    requestAnimationFrame(() => {
      bubble.classList.add("rising");
    });

    // Silent natural dissolution at the end of float
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

  function getModeLabel(m) {
    if (m === "off") return "OFF";
    if (m === "auto") return "AUTO (Decomp)";
    if (m === "on") return "ON (Always)";
    return "OFF";
  }

  function updateAllToggleUIs() {
    const textLabel = getModeLabel(mode);

    // 1. Poem Mode Toggle UI
    const poemLabel = document.getElementById("bubbles-mode-label");
    const poemDot = document.getElementById("bubble-dot-poem");
    if (poemLabel) poemLabel.textContent = textLabel;
    if (poemDot) {
      poemDot.className = `bubble-toggle-dot state-${mode}`;
    }

    // 2. Image Mode Toggle UI
    const imageLabel = document.getElementById("bubbles-mode-label-image");
    const imageDot = document.getElementById("bubble-dot-image");
    if (imageLabel) imageLabel.textContent = textLabel;
    if (imageDot) {
      imageDot.className = `bubble-toggle-dot state-${mode}`;
    }
  }

  function cycleMode() {
    // Cycle: OFF -> AUTO -> ON -> OFF
    if (mode === "off") mode = "auto";
    else if (mode === "auto") mode = "on";
    else mode = "off";

    localStorage.setItem(KEY, mode);
    updateAllToggleUIs();
    updateLoopState();

    if (window.DhritiAudio && typeof window.DhritiAudio.playClick === "function") {
      window.DhritiAudio.playClick();
    }
  }

  function wireToggles() {
    // Poem mode button
    const btnPoem = document.getElementById("btn-toggle-thought-bubbles");
    if (btnPoem && !btnPoem.dataset.wired) {
      btnPoem.dataset.wired = "true";
      btnPoem.addEventListener("click", (e) => {
        e.stopPropagation();
        cycleMode();
      });
    }

    // Image mode button
    const btnImage = document.getElementById("btn-toggle-bubbles-image");
    if (btnImage && !btnImage.dataset.wired) {
      btnImage.dataset.wired = "true";
      btnImage.addEventListener("click", (e) => {
        e.stopPropagation();
        cycleMode();
      });
    }

    updateAllToggleUIs();
  }

  function clearBubbles() {
    clearTimeout(spawnTimer);
    spawnTimer = null;
    if (layer) layer.innerHTML = "";
  }

  // Expose global controller
  window.DhritiBubbles = {
    getMode: () => mode,
    setMode: (newMode) => {
      mode = (newMode === "on" || newMode === "auto") ? newMode : "off";
      localStorage.setItem(KEY, mode);
      updateAllToggleUIs();
      updateLoopState();
    },
    cycleMode: cycleMode,
    spawnNow: (text) => spawnBubble(text),
    clear: clearBubbles,
    updateLoopState: updateLoopState,
    refreshFeed: refreshFeed
  };

  // --- Initialization ---
  function init() {
    wireToggles();
    refreshFeed();
    pollDecompressionState();
    setInterval(pollDecompressionState, 20000);
    setInterval(refreshFeed, 60000);
    updateLoopState();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
