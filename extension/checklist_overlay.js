/**
 * Dhriti Wall — Sticky-Note Checklist Overlay (C1/C2/C3).
 *
 * Runs inside a closed Shadow DOM on all browser pages.
 * Displays today's active study targets, shared Pomodoro, and quick park slot.
 * Collapses into a 2cm strip ({–} / {+}).
 */

(function () {
  // Avoid re-injecting on the same page
  if (document.getElementById("dhriti-overlay-host")) return;

  const host = document.createElement("div");
  host.id = "dhriti-overlay-host";
  // Start dormant (display:none) until active daemon and targets are verified
  host.style.cssText = "position:fixed;top:88px;right:18px;z-index:2147483646;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:none;";
  document.body.appendChild(host);

  const shadow = host.attachShadow({ mode: "closed" });

  const style = document.createElement("style");
  style.textContent = `
    * { box-sizing: border-box; margin: 0; padding: 0; }
    .overlay-card {
      background: rgba(20, 23, 38, 0.94);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 12px;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
      color: #e2e8f0;
      width: 320px;
      max-height: 75vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      user-select: none;
      transition: width 0.2s ease, max-height 0.2s ease, border-radius 0.2s ease;
    }
    .overlay-collapsed {
      width: 114px !important;
      height: 34px !important;
      max-height: 34px !important;
      border-radius: 17px;
      padding: 0;
      cursor: pointer;
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
      background: rgba(24, 28, 46, 0.96);
    }
    .overlay-collapsed:hover {
      background: rgba(35, 41, 68, 0.98);
      border-color: #8b78f6;
    }
    .overlay-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 12px;
      background: rgba(255, 255, 255, 0.04);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      cursor: grab;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.5px;
      color: #94a3b8;
    }
    .overlay-collapsed .overlay-header {
      border-bottom: none;
      padding: 6px 10px;
      height: 100%;
      cursor: pointer;
    }
    .overlay-collapsed .header-title {
      font-size: 11.5px;
      gap: 5px;
    }
    .overlay-collapsed .header-btn {
      font-size: 13px;
      font-weight: bold;
      color: #a78bfa;
      padding: 2px 4px;
      cursor: pointer;
    }
    .header-title {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #f1f5f9;
    }
    .header-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #8b78f6;
    }
    .header-btn {
      background: transparent;
      border: none;
      color: #94a3b8;
      cursor: pointer;
      font-size: 14px;
      padding: 2px 6px;
      border-radius: 4px;
      line-height: 1;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .header-btn:hover {
      background: rgba(255, 255, 255, 0.1);
      color: #fff;
    }
    .overlay-body {
      padding: 10px 12px;
      overflow-y: auto;
      max-height: 45vh;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .overlay-collapsed .overlay-body,
    .overlay-collapsed .overlay-footer {
      display: none !important;
    }
    .contract-label {
      font-size: 11px;
      color: #a78bfa;
      font-weight: 500;
      line-height: 1.3;
      padding: 4px 6px;
      background: rgba(139, 120, 246, 0.12);
      border-radius: 6px;
      border-left: 2px solid #8b78f6;
      margin-bottom: 4px;
    }
    .target-item {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 6px 8px;
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 8px;
      font-size: 12px;
      line-height: 1.35;
      color: #cbd5e1;
      transition: background 0.15s ease;
    }
    .target-item:hover {
      background: rgba(255, 255, 255, 0.06);
    }
    .target-check {
      cursor: pointer;
      font-size: 13px;
      color: #94a3b8;
      line-height: 1;
      margin-top: 1px;
    }
    .target-check.claimed { color: #f59e0b; }
    .target-check.verified { color: #10b981; }
    .target-title {
      flex: 1;
      word-break: break-word;
    }
    .overlay-footer {
      padding: 8px 12px;
      background: rgba(0, 0, 0, 0.2);
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .pomo-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 12px;
    }
    .pomo-time {
      font-family: monospace;
      font-size: 14px;
      font-weight: 700;
      color: #38bdf8;
    }
    .pomo-actions {
      display: flex;
      gap: 6px;
    }
    .pomo-btn {
      padding: 3px 8px;
      border-radius: 4px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      background: rgba(255, 255, 255, 0.06);
      color: #e2e8f0;
      font-size: 11px;
      cursor: pointer;
    }
    .pomo-btn:hover {
      background: rgba(255, 255, 255, 0.15);
    }
    .park-form {
      display: flex;
      gap: 6px;
    }
    .park-input {
      flex: 1;
      background: rgba(0, 0, 0, 0.35);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 6px;
      padding: 4px 8px;
      font-size: 11.5px;
      color: #f1f5f9;
      outline: none;
    }
    .park-input:focus {
      border-color: #8b78f6;
    }
    .park-btn {
      background: #8b78f6;
      border: none;
      color: #fff;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
    }
    .park-btn:hover {
      background: #7c3aed;
    }
  `;
  shadow.appendChild(style);

  const card = document.createElement("div");
  card.className = "overlay-card";

  // Build UI
  card.innerHTML = `
    <div class="overlay-header" id="drag-handle">
      <div class="header-title">
        <span class="header-dot"></span>
        <span id="header-text">Checklist</span>
      </div>
      <button class="header-btn" id="btn-toggle" title="Collapse / Expand (Alt+Shift+C)">{–}</button>
    </div>
    <div class="overlay-body">
      <div class="contract-label" id="contract-label">Loading today's target...</div>
      <div id="targets-list" style="display:flex;flex-direction:column;gap:6px;">
        <div style="font-size:11.5px;opacity:0.6;">Checking Dhriti daemon...</div>
      </div>
    </div>
    <div class="overlay-footer">
      <div class="pomo-bar">
        <span style="opacity:0.75;">Focus Timer</span>
        <span class="pomo-time" id="pomo-clock">25:00</span>
        <div class="pomo-actions">
          <button class="pomo-btn" id="btn-pomo-play">▶</button>
          <button class="pomo-btn" id="btn-pomo-reset">↺</button>
        </div>
      </div>
      <div class="park-form">
        <input type="text" class="park-input" id="park-input" placeholder="Park curiosity thought... (Alt+Shift+P)">
        <button class="park-btn" id="btn-park">Park</button>
      </div>
    </div>
  `;
  shadow.appendChild(card);

  // Dragging Implementation
  let isDragging = false;
  let offsetX = 0;
  let offsetY = 0;
  const handle = card.querySelector("#drag-handle");

  handle.addEventListener("mousedown", (e) => {
    if (e.target.tagName === "BUTTON") return;
    isDragging = true;
    offsetX = e.clientX - host.getBoundingClientRect().left;
    offsetY = e.clientY - host.getBoundingClientRect().top;
    handle.style.cursor = "grabbing";
  });

  window.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    const x = Math.max(10, Math.min(window.innerWidth - host.offsetWidth - 10, e.clientX - offsetX));
    const y = Math.max(10, Math.min(window.innerHeight - host.offsetHeight - 10, e.clientY - offsetY));
    host.style.left = x + "px";
    host.style.top = y + "px";
    host.style.right = "auto";
  });

  window.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      handle.style.cursor = "grab";
      try {
        chrome.storage.local.set({
          "dhriti_overlay_pos": { left: host.style.left, top: host.style.top }
        });
      } catch (e) {}
    }
  });

  // Collapse / Expand toggle
  const btnToggle = card.querySelector("#btn-toggle");
  let isCollapsed = false;

  function setCollapsed(collapse) {
    isCollapsed = collapse;
    if (isCollapsed) {
      card.classList.add("overlay-collapsed");
      card.title = "Click to expand checklist (Alt+Shift+C)";
      btnToggle.textContent = "⤢";
      btnToggle.title = "Expand Checklist";
    } else {
      card.classList.remove("overlay-collapsed");
      card.removeAttribute("title");
      btnToggle.textContent = "–";
      btnToggle.title = "Collapse Checklist (Alt+Shift+C)";
    }
    try {
      chrome.storage.local.set({ "dhriti_overlay_collapsed": isCollapsed });
    } catch (e) {}
  }

  // When collapsed, clicking ANYWHERE on the card or pellet expands it
  card.addEventListener("click", (e) => {
    if (isCollapsed && !isDragging) {
      setCollapsed(false);
    }
  });

  btnToggle.addEventListener("click", (e) => {
    e.stopPropagation();
    setCollapsed(!isCollapsed);
  });

  // Restore stored state
  try {
    chrome.storage.local.get(["dhriti_overlay_pos", "dhriti_overlay_collapsed"], (data) => {
      if (data.dhriti_overlay_pos) {
        if (data.dhriti_overlay_pos.left) host.style.left = data.dhriti_overlay_pos.left;
        if (data.dhriti_overlay_pos.top) host.style.top = data.dhriti_overlay_pos.top;
        host.style.right = "auto";
      }
      if (data.dhriti_overlay_collapsed) {
        setCollapsed(true);
      }
    });
  } catch (e) {}

  // Keyboard Shortcuts
  window.addEventListener("keydown", (e) => {
    if (e.altKey && e.shiftKey && (e.key === "C" || e.key === "c")) {
      setCollapsed(!isCollapsed);
    }
    if (e.altKey && e.shiftKey && (e.key === "P" || e.key === "p")) {
      if (isCollapsed) setCollapsed(false);
      const parkInp = card.querySelector("#park-input");
      if (parkInp) parkInp.focus();
    }
  });

  // Targets & State Fetch
  function refreshTargets() {
    try {
      chrome.runtime.sendMessage({ type: "get_targets" }, (res) => {
        // If bridge is offline or daemon not responding, stay dormant and invisible
        if (!res || !res.ok) {
          host.style.display = "none";
          return;
        }

        const targets = res.targets || [];
        const isSealed = Boolean(res.sealed);

        // If no contract sealed and no targets declared, remain dormant outside enforcement
        if (!isSealed && targets.length === 0) {
          host.style.display = "none";
          return;
        }

        // Active study day verified: display the overlay
        host.style.display = "block";

        const contractLabel = card.querySelector("#contract-label");
        const list = card.querySelector("#targets-list");
        if (contractLabel) {
          contractLabel.textContent = res.contract_line || (isSealed ? "Active Contract Sealed" : "Daily Targets");
        }

        if (list) {
          list.innerHTML = "";
          if (targets.length === 0) {
            list.innerHTML = `<div style="font-size:11.5px;opacity:0.65;padding:4px;">No active targets. Open dashboard ritual to set targets.</div>`;
            return;
          }

          targets.forEach((t, i) => {
            const item = document.createElement("div");
            item.className = "target-item";
            const state = t.state || "pending";
            const icon = state === "verified" ? "☑" : state === "claimed" ? "◐" : "☐";
            const iconClass = state;

            item.innerHTML = `
              <span class="target-check ${iconClass}" data-idx="${i}">${icon}</span>
              <span class="target-title">${escapeText(t.label || "Target " + (i + 1))}</span>
            `;

            const checkBtn = item.querySelector(".target-check");
            checkBtn.addEventListener("click", () => {
              if (state === "pending") {
                chrome.runtime.sendMessage({
                  type: "claim_target",
                  target_id: t.id || "target-" + i,
                  label: t.label
                }, () => refreshTargets());
              }
            });

            list.appendChild(item);
          });
        }
      });
    } catch (e) {
      host.style.display = "none";
    }
  }

  // Quick Park Submission
  const btnPark = card.querySelector("#btn-park");
  const parkInput = card.querySelector("#park-input");

  function submitPark() {
    const text = (parkInput.value || "").trim();
    if (!text) return;
    btnPark.disabled = true;
    btnPark.textContent = "...";
    try {
      chrome.runtime.sendMessage({
        type: "quick_park",
        text: text,
        site: window.location.hostname
      }, (res) => {
        btnPark.disabled = false;
        btnPark.textContent = "Park";
        if (res && res.ok) {
          parkInput.value = "";
          parkInput.placeholder = "Parked for 20:00!";
          setTimeout(() => { parkInput.placeholder = "Park curiosity thought... (Alt+Shift+P)"; }, 2500);
        }
      });
    } catch (e) {
      btnPark.disabled = false;
      btnPark.textContent = "Park";
    }
  }

  if (btnPark && parkInput) {
    btnPark.addEventListener("click", submitPark);
    parkInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submitPark();
    });
  }

  // Pomodoro Timer
  let pomoSeconds = 25 * 60;
  let pomoRunning = false;
  let pomoInterval = null;
  const pomoClock = card.querySelector("#pomo-clock");
  const btnPomoPlay = card.querySelector("#btn-pomo-play");
  const btnPomoReset = card.querySelector("#btn-pomo-reset");

  function renderClock() {
    const m = Math.floor(pomoSeconds / 60).toString().padStart(2, "0");
    const s = (pomoSeconds % 60).toString().padStart(2, "0");
    if (pomoClock) pomoClock.textContent = `${m}:${s}`;
  }

  if (btnPomoPlay) {
    btnPomoPlay.addEventListener("click", () => {
      pomoRunning = !pomoRunning;
      btnPomoPlay.textContent = pomoRunning ? "⏸" : "▶";
      if (pomoRunning) {
        pomoInterval = setInterval(() => {
          if (pomoSeconds > 0) {
            pomoSeconds--;
            renderClock();
          } else {
            clearInterval(pomoInterval);
            pomoRunning = false;
            btnPomoPlay.textContent = "▶";
            pomoSeconds = 5 * 60; // 5 min break
            renderClock();
          }
        }, 1000);
      } else {
        clearInterval(pomoInterval);
      }
    });
  }

  if (btnPomoReset) {
    btnPomoReset.addEventListener("click", () => {
      clearInterval(pomoInterval);
      pomoRunning = false;
      if (btnPomoPlay) btnPomoPlay.textContent = "▶";
      pomoSeconds = 25 * 60;
      renderClock();
    });
  }

  function escapeText(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  // Initial load
  refreshTargets();
  // Periodic poll every 45s
  setInterval(refreshTargets, 45000);

})();
