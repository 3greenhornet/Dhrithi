/**
 * Dhriti Extension Popup & Tab Dashboard Controller.
 * Fully compatible with MV3 extension action popup or local tab.
 */
(() => {
  "use strict";

  const BRIDGE_URL = "http://127.0.0.1:7311";

  const urlParams = new URLSearchParams(window.location.search);
  const paramToken = urlParams.get("token");

  const state = {
    connected: false,
    token: paramToken || (function() {
      try { return localStorage.getItem("dhriti_token") || ""; } catch (e) { return ""; }
    })(),
    day: { state: "OPEN", bounds: "10:00–21:00" },
    session: {
      active: false,
      id: null,
      task: "No active session",
      capsule: null,
      started_at: null,
      duration_minutes: 50
    },
    guard: {
      mode: "checkpoint",
      budget_used: 0,
      budget_limit: 15,
      burst_active_until: 0,
      sends_in_window: 0,
      burst_toll_s: 10,
      sidecar_armed: false
    },
    activeDrawer: null
  };

  const el = {
    dot: document.getElementById("bridge-dot"),
    meta: document.getElementById("bridge-meta"),
    dayBadge: document.getElementById("day-badge"),
    guardBadge: document.getElementById("guard-badge"),
    sessionState: document.getElementById("session-state"),
    sessionText: document.getElementById("session-state-text"),
    windowBounds: document.getElementById("window-bounds"),
    timerDigits: document.getElementById("timer-display"),
    timerLabel: document.getElementById("timer-label"),
    sessionProgress: document.getElementById("session-progress"),
    sessionTask: document.getElementById("session-task-text"),
    btnSession: document.getElementById("btn-session"),
    btnSessionText: document.getElementById("btn-session-text"),
    btnSessionIcon: document.getElementById("btn-session-icon"),
    btnPark: document.getElementById("btn-park"),
    btnLeisure: document.getElementById("btn-leisure"),
    btnResearch: document.getElementById("btn-research"),
    drawer: document.getElementById("action-drawer"),
    drawerTitle: document.getElementById("drawer-title"),
    drawerInput: document.getElementById("drawer-input"),
    drawerCancel: document.getElementById("drawer-cancel"),
    drawerSubmit: document.getElementById("drawer-submit"),
    sidecarStatus: document.getElementById("sidecar-status"),
    budgetRatio: document.getElementById("budget-ratio"),
    budgetVal: document.getElementById("budget-val"),
    budgetBar: document.getElementById("budget-bar"),
    burstCount: document.getElementById("burst-count"),
    burstStatus: document.getElementById("burst-status"),
    burstBar: document.getElementById("burst-bar"),
    toast: document.getElementById("toast")
  };

  // -------------------------------------------------------------
  // Bridge Client: chrome.runtime with direct loopback fallback
  // -------------------------------------------------------------
  async function bridgeFetch(endpoint, method = "GET", body = null) {
    if (typeof chrome !== "undefined" && chrome.runtime?.sendMessage) {
      return new Promise((resolve) => {
        chrome.runtime.sendMessage(
          { type: "BRIDGE_REQ", endpoint, method, body },
          (res) => {
            if (chrome.runtime.lastError || !res) {
              directFetch(endpoint, method, body).then(resolve);
            } else {
              resolve(res);
            }
          }
        );
      });
    }
    return directFetch(endpoint, method, body);
  }

  async function directFetch(endpoint, method = "GET", body = null) {
    try {
      const res = await fetch(BRIDGE_URL + endpoint, {
        method,
        headers: {
          "Content-Type": "application/json",
          "X-Dhriti-Token": state.token
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(1800)
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      state.connected = true;
      return data;
    } catch (e) {
      state.connected = false;
      return null;
    }
  }

  // -------------------------------------------------------------
  // Renderers
  // -------------------------------------------------------------
  function showToast(msg) {
    el.toast.textContent = msg;
    el.toast.style.display = "block";
    clearTimeout(el.toast._t);
    el.toast._t = setTimeout(() => { el.toast.style.display = "none"; }, 2500);
  }

  function renderStatus() {
    if (state.connected) {
      el.dot.className = "brand-dot";
      el.meta.textContent = "127.0.0.1:7311";
    } else {
      el.dot.className = "brand-dot offline";
      el.meta.textContent = "127.0.0.1:7311 [LOCAL]";
    }
    el.dayBadge.textContent = `DAY: ${state.day.state.toUpperCase()}`;
    el.guardBadge.textContent = state.guard.mode.toUpperCase();
  }

  function renderSession() {
    const capBox = document.getElementById("capsule-box");
    const capNext = document.getElementById("capsule-next");

    if (!state.session.active) {
      el.sessionText.textContent = "IDLE";
      el.sessionState.style.color = "var(--text-muted)";
      el.sessionState.querySelector(".pip").style.background = "var(--text-muted)";
      el.sessionState.querySelector(".pip").style.animation = "none";
      el.timerDigits.textContent = "--:--";
      el.timerLabel.textContent = "No Active Session";
      el.sessionProgress.style.width = "0%";
      el.sessionTask.textContent = "(No session active. Click 'Start Session')";
      el.btnSessionText.textContent = "Start Session";
      el.btnSessionIcon.textContent = "▶";
      if (capBox) capBox.style.display = "none";
      return;
    }

    el.sessionText.textContent = "ACTIVE";
    el.sessionState.style.color = "var(--green)";
    el.sessionState.querySelector(".pip").style.background = "var(--green)";
    el.sessionState.querySelector(".pip").style.animation = "pulse 2s infinite ease-in-out";
    el.btnSessionText.textContent = "End / Proof";
    el.btnSessionIcon.textContent = "✓";
    el.sessionTask.textContent = state.session.task;

    if (capBox && capNext) {
      if (state.session.capsule && state.session.capsule.next_action) {
        capBox.style.display = "block";
        capNext.textContent = state.session.capsule.next_action;
      } else {
        capBox.style.display = "none";
      }
    }
  }

  function updateCountdown() {
    if (!state.session.active || !state.session.started_at) return;
    const totalMs = state.session.duration_minutes * 60 * 1000;
    const elapsed = Date.now() - state.session.started_at;
    const remaining = Math.max(0, totalMs - elapsed);
    const sec = Math.floor(remaining / 1000);

    const m = Math.floor(sec / 60);
    const s = sec % 60;
    el.timerDigits.textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;

    const pct = Math.min(100, Math.max(0, (elapsed / totalMs) * 100));
    el.sessionProgress.style.width = `${pct.toFixed(1)}%`;

    if (sec === 0) {
      el.timerLabel.textContent = "Target Elapsed";
      el.timerDigits.style.color = "var(--amber)";
    } else {
      el.timerLabel.textContent = "Remaining";
      el.timerDigits.style.color = "var(--text)";
    }
  }

  function renderGuard() {
    const g = state.guard;
    const rem = Math.max(0, g.budget_limit - g.budget_used);
    el.budgetRatio.textContent = `${rem} / ${g.budget_limit}`;
    el.budgetVal.textContent = `${rem} rem`;
    const budgetPct = (rem / g.budget_limit) * 100;
    el.budgetBar.style.width = `${budgetPct}%`;
    el.budgetBar.className = budgetPct <= 20 ? "mini-bar-fill bar-amber" : "mini-bar-fill bar-blue";

    const now = Date.now();
    const isBursting = g.burst_active_until > now;
    el.burstCount.textContent = `${g.sends_in_window} in 10m`;
    if (isBursting) {
      const tollRem = Math.ceil((g.burst_active_until - now) / 1000);
      el.burstStatus.className = "cell-val tag-cooldown";
      el.burstStatus.textContent = `● Toll (${tollRem}s)`;
      el.burstBar.style.background = "var(--amber)";
      el.burstBar.style.width = `${Math.min(100, (tollRem / g.burst_toll_s) * 100)}%`;
    } else {
      el.burstStatus.className = "cell-val tag-idle";
      el.burstStatus.textContent = "● Idle (0s)";
      el.burstBar.style.background = "var(--green)";
      el.burstBar.style.width = "100%";
    }

    el.sidecarStatus.innerHTML = `Sidecar: ${g.sidecar_armed ? '<b style="color:var(--green)">ARMED</b>' : 'OFFLINE'}`;
  }

  // -------------------------------------------------------------
  // Drawer Interactions
  // -------------------------------------------------------------
  function openDrawer(action) {
    state.activeDrawer = action;
    el.drawer.classList.add("active");
    if (action === "park") {
      el.drawerTitle.textContent = "Park a Thought (Cold Deferral)";
      el.drawerInput.placeholder = "Enter question or thought to defer...";
    } else if (action === "leisure") {
      el.drawerTitle.textContent = "Declare Leisure (Rest, Not Drift)";
      el.drawerInput.placeholder = "Activity (e.g., coffee walk, 15m)...";
    } else if (action === "research") {
      el.drawerTitle.textContent = "Quick Research Pass (15m Bounded)";
      el.drawerInput.placeholder = "Specific research question / docs...";
    } else if (action === "session") {
      if (state.session.active) {
        el.drawerTitle.textContent = "End Session (Submit Proof)";
        el.drawerInput.placeholder = "Proof notes or command outcome...";
      } else {
        el.drawerTitle.textContent = "Start Session (Commit Line)";
        el.drawerInput.placeholder = "Task statement (one clear line)...";
      }
    }
    el.drawerInput.value = "";
    el.drawerInput.focus();
  }

  function closeDrawer() {
    state.activeDrawer = null;
    el.drawer.classList.remove("active");
    el.drawerInput.value = "";
  }

  async function handleDrawerSubmit() {
    const val = el.drawerInput.value.trim();
    if (!val) return;
    const action = state.activeDrawer;
    closeDrawer();

    if (action === "park") {
      await bridgeFetch("/guard/park", "POST", { text: val, site: "dashboard" });
      showToast(`Parked: "${val.slice(0, 20)}..." → review`);
    } else if (action === "leisure") {
      await bridgeFetch("/events", "POST", { type: "leisure_declared", activity: val });
      showToast(`Leisure recorded: "${val.slice(0, 20)}"`);
    } else if (action === "research") {
      state.guard.budget_used = Math.min(state.guard.budget_limit, state.guard.budget_used + 1);
      renderGuard();
      showToast("Research pass active: 15m allowance (-1 budget)");
    } else if (action === "session") {
      if (state.session.active) {
        state.session.active = false;
        renderSession();
        showToast("Session finished. Outcome recorded.");
      } else {
        state.session.active = true;
        state.session.task = val;
        state.session.started_at = Date.now();
        state.session.duration_minutes = 50;
        renderSession();
        updateCountdown();
        showToast(`Session started: "${val.slice(0, 20)}"`);
      }
    }
  }

  // -------------------------------------------------------------
  // Data Sync
  // -------------------------------------------------------------
  async function syncState() {
    const status = await bridgeFetch("/status");
    if (status) {
      state.connected = true;
      if (status.active_session && status.session_topic) {
        state.session.active = true;
        state.session.id = status.active_session;
        state.session.task = status.session_topic.topic || state.session.task;
        state.session.capsule = status.session_topic.resume_capsule || null;
      } else {
        state.session.active = false;
        state.session.capsule = null;
      }
    }
    const guard = await bridgeFetch("/guard/state");
    if (guard?.snapshot) {
      state.guard.mode = guard.mode || state.guard.mode;
      state.guard.budget_used = guard.snapshot.prompt_budget_used;
      state.guard.budget_limit = guard.snapshot.prompt_budget_limit;
      state.guard.sidecar_armed = guard.snapshot.sidecar_armed;
    }
    renderStatus();
    renderSession();
    renderGuard();
  }

  // Event bindings
  el.btnSession.addEventListener("click", () => openDrawer("session"));
  el.btnPark.addEventListener("click", () => openDrawer("park"));
  el.btnLeisure.addEventListener("click", () => openDrawer("leisure"));
  el.btnResearch.addEventListener("click", () => openDrawer("research"));
  el.drawerCancel.addEventListener("click", closeDrawer);
  el.drawerSubmit.addEventListener("click", handleDrawerSubmit);
  el.drawerInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleDrawerSubmit();
    if (e.key === "Escape") closeDrawer();
  });

  // Ticking Loops
  syncState();
  setInterval(updateCountdown, 1000);
  setInterval(renderGuard, 1000);
  setInterval(syncState, 15000);
})();

