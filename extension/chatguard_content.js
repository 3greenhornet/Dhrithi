/*
 * chatguard_content.js -- Dhriti Guard Kit, content script (plain MV3).
 *
 * Responsibilities (all under the guard's mode policy from /guard/state):
 *   1. Send gate       : capture-phase interception of Enter / send click;
 *                        asks the background (which asks the bridge) BEFORE
 *                        the prompt leaves. HOLD/PARK => preventDefault.
 *   2. Transcript truth: DOM diff of user messages (the button is not the
 *                        only send path -- edit-resend, regenerate, chips).
 *                        Unapproved sends => leak report => collapse-seal.
 *   3. Collapse-and-seal: held responses collapse to a one-line neutral
 *                        card; content stays in DOM (display:none) for the
 *                        cold reveal; blur is NOT used (blur leaks the
 *                        first line and the structure).
 *   4. Length governor : responses beyond the char limit collapse their
 *                        tail behind an expand-toll (D-073, L-4-pure).
 *   5. DOM canary      : hidden marker at arm-time; disappearance is
 *                        reported (D-081 fail-visible blindness).
 *   6. Chip suppression: AI follow-up chips are a recommendation surface
 *                        (their D-032/D-024) -- hidden per adapter config.
 *
 * L-2: card lines come from the bridge (facts only). L-1: no engagement
 * beyond Park / Toll / Cancel. L-4 default: text is hashed locally; the
 * raw text only reaches the loopback sidecar when the sidecar is armed.
 */

(() => {
  "use strict";

  // ------------------------------------------------------------------
  // SITE ADAPTER REGISTRY -- THE PLUGIN SLOT. Add a site by adding an
  // object here; see SITE_ADAPTERS.md for the field contract. Selectors
  // rot; probe() + the DOM canary make staleness loud, not silent.
  // ------------------------------------------------------------------
  const ADAPTERS = {
    chatgpt: {
      site: "chatgpt",
      input: "div#prompt-textarea, textarea[data-id='root'], textarea",
      sendBtn: "button[data-testid='send-button'], button[aria-label*='Send']",
      transcript: "main, [class*='react-scroll-to-bottom']",
      userMsg: "[data-message-author-role='user']",
      assistantMsg: "[data-message-author-role='assistant']",
      chips: "[data-testid*='suggestion'], button[aria-label*='sugges']",
      stopBtn: "button[aria-label*='Stop'], button[data-testid='stop-button']",
    },
    gemini: {
      site: "gemini",
      // Gemini nests deep in open shadow roots; pierce() handles it.
      input: "rich-textarea .ql-editor[contenteditable='true'], div[contenteditable='true'][role='textbox']",
      sendBtn: "button[aria-label*='Send'], button.send-button",
      transcript: "chat-window, main",
      userMsg: "user-query, .user-query-container",
      assistantMsg: "model-response, .model-response-container, message-content",
      chips: "suggestion-chip, chips-row",
      stopBtn: "button[aria-label*='Stop']",
    },
    deepseek: {
      site: "deepseek",
      input: "textarea#chat-input, textarea",
      sendBtn: "div[role='button'][aria-disabled='false']:has(svg), button:has(svg[aria-label='send'])",
      transcript: ".ds-chat-window, main",
      userMsg: ".ds-message--user, div[class*='user']",
      assistantMsg: ".ds-message--assistant, div[class*='assistant']",
      chips: "div[class*='suggestion']",
      stopBtn: "div[role='button'][aria-label*='stop' i], button[aria-label*='stop' i]",
    },
    claude: {
      site: "claude",
      input: "div[contenteditable='true'].ProseMirror, fieldset div[contenteditable='true']",
      sendBtn: "button[aria-label*='Send Message'], button[type='submit']",
      transcript: "main .flex.flex-col",
      userMsg: "[data-testid='user-message'], .font-user-message",
      assistantMsg: "[data-testid='assistant-message'], .font-claude-message",
      chips: "button[data-testid*='suggestion']",
      stopBtn: "button[aria-label*='Stop'], button[data-testid='stop']",
    },
    generic: {  // fallback: Enter-count + transcript-diff heuristics only
      site: "generic",
      input: "textarea, div[contenteditable='true'][role='textbox']",
      sendBtn: "button[type='submit'], button[aria-label*='Send']",
      transcript: "main",
      userMsg: null,
      assistantMsg: null,
      chips: null,
      stopBtn: "button[aria-label*='Stop']",
    },
  };

  function pickAdapter() {
    const h = location.hostname;
    if (h.includes("chatgpt.com") || h.includes("chat.openai.com")) return ADAPTERS.chatgpt;
    if (h.includes("gemini.google.com")) return ADAPTERS.gemini;
    if (h.includes("chat.deepseek.com")) return ADAPTERS.deepseek;
    if (h.includes("claude.ai")) return ADAPTERS.claude;
    return ADAPTERS.generic;
  }

  // ------------------------------------------------------------------
  // helpers
  // ------------------------------------------------------------------
  const qsa = (root, sel) => (root ? Array.from(root.querySelectorAll(sel)) : []);
  const SHA = (s) => {
    let h = 5381;
    for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
    return "h" + h.toString(16) + "-" + s.length;
  };
  // pierce open shadow roots (Gemini)
  function pierce(rootSel) {
    const direct = qsa(document, rootSel);
    if (direct.length) return direct;
    const out = [];
    const walk = (node) => {
      if (!node) return;
      if (node.shadowRoot) {
        out.push(...qsa(node.shadowRoot, rootSel));
        node.shadowRoot.querySelectorAll("*").forEach(walk);
      } else if (node.querySelectorAll) {
        node.querySelectorAll("*").forEach((c) => { if (c.shadowRoot) walk(c); });
      }
    };
    document.body.querySelectorAll("*").forEach(walk);
    return out;
  }
  const findFirst = (sel) => {
    if (!sel) return null;
    return qsa(document, sel)[0] || pierce(sel)[0] || null;
  };

  const S = {
    adapter: pickAdapter(),
    armed: false,
    policy: { mode: "checkpoint", prompt_budget_limit: 15, length_limit_chars: 300, collapse_hint: true },
    approved: new Set(),      // prompt hashes allowed this load
    sealed: new Set(),        // assistant nodes already collapse-sealed
    userMsgSeen: new Set(),   // user message hashes already known
    cardEl: null,
  };

  const send = (msg) => new Promise((res) => {
    try { chrome.runtime.sendMessage(msg, (r) => { void chrome.runtime.lastError; res(r || {}); }); }
    catch (e) { res({}); }
  });

  // ------------------------------------------------------------------
  // CSS -- sealed envelope style. Neutral, boring (Wall Principle).
  // ------------------------------------------------------------------
  const style = document.createElement("style");
  style.textContent = `
    .dhriti-sealed { position: relative; }
    .dhriti-sealed > *:not(.dhriti-card) { display: none !important; }
    .dhriti-card {
      display: flex; gap: 12px; align-items: center; justify-content: space-between;
      padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px;
      background: #f8fafc; color: #334155; font: 13px/1.4 system-ui, sans-serif;
    }
    .dhriti-card .dhriti-lines { display: flex; flex-direction: column; gap: 2px; }
    .dhriti-card button {
      border: 1px solid #94a3b8; background: #fff; color: #334155;
      border-radius: 6px; padding: 4px 10px; cursor: pointer; font: 12px system-ui;
    }
    .dhriti-card button:disabled { opacity: .5; cursor: default; }
    .dhriti-hidden-chip { display: none !important; }
    .dhriti-canary { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
    .dhriti-tail-dim { opacity: 0.35 !important; filter: blur(1.5px); transition: opacity 0.25s ease, filter 0.25s ease !important; }
    .dhriti-tail-dim:hover { opacity: 1 !important; filter: none !important; }
  `;
  document.documentElement.appendChild(style);

  // ------------------------------------------------------------------
  // probe + DOM canary (fail-visible blindness, D-077 / D-081)
  // ------------------------------------------------------------------
  async function probe() {
    const input = findFirst(S.adapter.input);
    const sendBtn = findFirst(S.adapter.sendBtn);
    const transcript = findFirst(S.adapter.transcript);
    const missing = [];
    if (!input) missing.push("input");
    if (!sendBtn) missing.push("send_button");
    if (!transcript) missing.push("transcript");
    S.armed = missing.length === 0;
    await send({ type: "guard_probe", site: S.adapter.site, ok: S.armed,
                 missing, detail: missing.join(",") });
    if (transcript && !document.querySelector(".dhriti-canary")) {
      const c = document.createElement("span");
      c.className = "dhriti-canary";
      c.setAttribute("data-dhriti-canary", "1");
      transcript.appendChild(c);
    }
    return S.armed;
  }

  function checkCanary() {
    const alive = !!document.querySelector("[data-dhriti-canary]");
    if (!alive && S.armed) {
      send({ type: "guard_canary_missing", site: S.adapter.site,
             detail: "DOM canary removed mid-session; selectors likely stale" });
    }
  }

  // ------------------------------------------------------------------
  // hold card (neutral; lines are facts from the bridge)
  // ------------------------------------------------------------------
  function showCard(lines, { tollSeconds = 0, onPark, onSend, onCancel } = {}) {
    hideCard();
    const el = document.createElement("div");
    el.className = "dhriti-card";
    el.style.cssText = "position:fixed;right:18px;bottom:88px;z-index:2147483647;max-width:380px;";
    const linesBox = document.createElement("div");
    linesBox.className = "dhriti-lines";
    (lines && lines.length ? lines : ["Held."]).forEach((t) => {
      const p = document.createElement("span");
      p.textContent = t;             // textContent only: never innerHTML
      linesBox.appendChild(p);
    });
    const btns = document.createElement("div");
    btns.style.cssText = "display:flex;gap:6px;";
    const mkBtn = (label, fn, dis = false) => {
      const b = document.createElement("button");
      b.textContent = label; b.disabled = dis;
      b.addEventListener("click", () => fn && fn());
      return b;
    };
    const parkBtn = mkBtn("Park", () => { hideCard(); onPark && onPark(); });
    const tollBtn = mkBtn(tollSeconds ? `Send (${tollSeconds}s)` : "Send",
      () => { hideCard(); onSend && onSend(); }, true);
    const allowBtn = mkBtn("Allow & Learn", () => { hideCard(); onAllowSafe && onAllowSafe(); });
    allowBtn.style.cssText = "font-size:11px;padding:3px 7px;background:#1a2b1a;border:1px solid #2d5a2d;color:#7ec87e;border-radius:3px;cursor:pointer;";
    const cancelBtn = mkBtn("Cancel", () => { hideCard(); onCancel && onCancel(); });
    btns.append(parkBtn, tollBtn, allowBtn, cancelBtn);
    el.append(linesBox, btns);
    document.body.appendChild(el);
    S.cardEl = el;
    if (tollSeconds > 0) {
      let left = tollSeconds;
      const iv = setInterval(() => {
        left -= 1;
        tollBtn.textContent = `Send (${left}s)`;
        if (left <= 0) { clearInterval(iv); tollBtn.disabled = false; tollBtn.textContent = "Send"; }
      }, 1000);
      el.dataset.iv = String(iv);
    }
    return el;
  }
  function hideCard() {
    if (S.cardEl) { clearInterval(Number(S.cardEl.dataset.iv || 0)); S.cardEl.remove(); S.cardEl = null; }
  }

  // ------------------------------------------------------------------
  // send gate
  // ------------------------------------------------------------------
  function currentPrompt(input) {
    return input ? (input.value !== undefined && input.value !== ""
      ? String(input.value)
      : String(input.innerText || input.textContent || "")).trim() : "";
  }

  async function gateSend(input, ev) {
    const text = currentPrompt(input);
    if (!text) return false;
    const promptHash = SHA(text);
    const threadId = threadIdentity();
    const resp = await send({ type: "guard_send", site: S.adapter.site,
                              thread_id: threadId, prompt_hash: promptHash,
                              preview_len: text.length, prompt_text: text });
    const action = resp.action || "send";
    if (action === "send") {
      S.approved.add(promptHash);
      return false;                       // let it through
    }
    if (ev) { ev.preventDefault(); ev.stopImmediatePropagation(); }
    showCard(resp.card_lines || ["Held by Dhriti."], {
      tollSeconds: resp.toll_seconds || 0,
      onPark: async () => {
        await send({ type: "guard_park", site: S.adapter.site,
                     thread_id: threadId, prompt_hash: promptHash, text });
        try { input.value = ""; input.innerText = ""; } catch (e) {}
      },
      onSend: async () => {
        await send({ type: "guard_toll_paid", site: S.adapter.site,
                     thread_id: threadId, prompt_hash: promptHash });
        S.approved.add(promptHash);
        clickSend(input);
      },
      onAllowSafe: async () => {
        await send({ type: "guard_learn_safe", site: S.adapter.site,
                     thread_id: threadId, prompt_hash: promptHash, text });
        S.approved.add(promptHash);
        clickSend(input);
      },
      onCancel: async () => {
        await send({ type: "guard_override", site: S.adapter.site,
                     thread_id: threadId, prompt_hash: promptHash });
      },
    });
    return true;                          // we intercepted
  }

  function clickSend(input) {
    const btn = findFirst(S.adapter.sendBtn);
    if (btn) { btn.click(); return; }
    // last resort: synthetic Enter on the input
    const kbd = new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true });
    (input || document.activeElement).dispatchEvent(kbd);
  }

  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" || ev.shiftKey || ev.isComposing) return;
    const t = ev.target;
    const isInput = t && (t.matches?.(S.adapter.input) ||
      (t.closest && t.closest(S.adapter.input)));
    if (!isInput) return;
    gateSend(t, ev);
  }, true);

  document.addEventListener("click", (ev) => {
    const btn = ev.target && ev.target.closest?.(S.adapter.sendBtn);
    if (!btn) return;
    const input = findFirst(S.adapter.input);
    gateSend(input, ev);
  }, true);

  // ------------------------------------------------------------------
  // thread identity + interlock (D-082)
  // ------------------------------------------------------------------
  function threadIdentity() {
    // URL path is the honest thread key on all four sites.
    return location.pathname.length > 1 ? location.pathname : "/new";
  }
  let lastThread = threadIdentity();
  async function checkThreadChange() {
    const cur = threadIdentity();
    if (cur !== lastThread) {
      const resp = await send({ type: "guard_thread_open", site: S.adapter.site, thread_id: cur });
      lastThread = cur;
      S.approved.clear(); S.userMsgSeen.clear();
      if (resp && resp.allowed === false) {
        showCard(resp.card_lines || ["Dispose current thread first."], {});
      }
    }
  }
  setInterval(checkThreadChange, 1500);

  // ------------------------------------------------------------------
  // transcript truth: diff user messages (leak detection)
  // ------------------------------------------------------------------
  async function diffTranscript() {
    const transcript = findFirst(S.adapter.transcript);
    if (!transcript || !S.adapter.userMsg) return;
    const users = [...qsa(transcript, S.adapter.userMsg), ...pierce(S.adapter.userMsg)];
    for (const u of users) {
      const text = (u.innerText || "").trim();
      if (!text) continue;
      const h = SHA(text);
      if (S.userMsgSeen.has(h)) continue;
      S.userMsgSeen.add(h);
      if (!S.approved.has(h)) {
        // leak: entered without the gate (edit-resend, regenerate, chip)
        const resp = await send({ type: "guard_leak", site: S.adapter.site,
                                  thread_id: threadIdentity(), prompt_hash: h });
        if (resp.collapse) collapseSeal(nearestAssistant(u) || transcript);
      }
    }
  }

  function nearestAssistant(userEl) {
    if (!S.adapter.assistantMsg) return null;
    let n = userEl.nextElementSibling;
    for (let i = 0; n && i < 4; i++, n = n.nextElementSibling) {
      if (n.matches?.(S.adapter.assistantMsg)) return n;
    }
    return qsa(document, S.adapter.assistantMsg).slice(-1)[0] ||
           pierce(S.adapter.assistantMsg).slice(-1)[0] || null;
  }

  // ------------------------------------------------------------------
  // collapse-and-seal + length governor (D-071 / D-073)
  // ------------------------------------------------------------------
  function collapseSeal(el) {
    if (!el || S.sealed.has(el)) return;
    S.sealed.add(el);
    el.classList.add("dhriti-sealed");
    const card = document.createElement("div");
    card.className = "dhriti-card dhriti-overlay";
    const lines = document.createElement("div");
    lines.className = "dhriti-lines";
    const l1 = document.createElement("span");
    l1.textContent = "Held by Dhriti.";
    const l2 = document.createElement("span");
    l2.textContent = "Content preserved. Reveal at cold review.";
    lines.append(l1, l2);
    const reveal = document.createElement("button");
    reveal.textContent = "Request reveal";
    reveal.addEventListener("click", async () => {
      const resp = await send({ type: "guard_reveal_request", site: S.adapter.site,
                                thread_id: threadIdentity() });
      if (resp.allow) { el.classList.remove("dhriti-sealed"); card.remove(); }
      else { l2.textContent = resp.card_line || "Reveal at checkpoint."; }
    });
    card.append(lines, reveal);
    el.prepend(card);
    send({ type: "guard_response_hidden", site: S.adapter.site,
           thread_id: threadIdentity() });
  }

  function lengthGovernor() {
    if (!S.adapter.assistantMsg) return;
    const limit = Number(S.policy.length_limit_chars || 0);
    if (!limit) return;
    const msgs = [...qsa(document, S.adapter.assistantMsg), ...pierce(S.adapter.assistantMsg)];
    const last = msgs[msgs.length - 1];
    if (!last || S.sealed.has(last)) return;
    const len = (last.innerText || "").length;
    if (len > limit * 3) collapseSeal(last);   // structural cap, content-blind
  }

  // ------------------------------------------------------------------
  // chips suppression (D-032: chips are a recommendation surface)
  // ------------------------------------------------------------------
  function suppressChips() {
    if (!S.adapter.chips) return;
    [...qsa(document, S.adapter.chips), ...pierce(S.adapter.chips)]
      .forEach((c) => c.classList.add("dhriti-hidden-chip"));
  }

  // ------------------------------------------------------------------
  // completion tail governor (dimming trailing AI engagement hooks)
  // ------------------------------------------------------------------
  const TAIL_HOOKS = [
    /^(would you like (me to|to)|shall (i|we)|let me know if you('d| would)? like|do you want (me to|to)|feel free to ask|if you('d| would)? like, (we|i) can)/i,
    /^(next steps?:|should we (also|now)|would it be helpful if|is there anything else)/i
  ];

  function dimCompletionTails() {
    if (!S.adapter.assistantMsg) return;
    const msgs = [...qsa(document, S.adapter.assistantMsg), ...pierce(S.adapter.assistantMsg)];
    if (!msgs.length) return;
    const lastMsg = msgs[msgs.length - 1];
    if (S.sealed.has(lastMsg)) return;

    const blocks = lastMsg.querySelectorAll("p, li");
    if (!blocks.length) return;
    const lastBlock = blocks[blocks.length - 1];
    if (lastBlock.dataset && lastBlock.dataset.dhritiTailChecked) return;
    if (lastBlock.dataset) lastBlock.dataset.dhritiTailChecked = "true";

    const text = (lastBlock.textContent || "").trim();
    if (TAIL_HOOKS.some((rgx) => rgx.test(text))) {
      lastBlock.classList.add("dhriti-tail-dim");
      lastBlock.title = "Conversational engagement tail dimmed by Dhriti (hover to unmask)";
    }
  }

  // ------------------------------------------------------------------
  // observers + timers
  // ------------------------------------------------------------------
  const mo = new MutationObserver(() => {
    suppressChips();
    dimCompletionTails();
    checkCanary();
    lengthGovernor();
    diffTranscript();
  });
  function start() {
    probe().then(() => {
      mo.observe(document.body, { childList: true, subtree: true, characterData: true });
      setInterval(() => { suppressChips(); dimCompletionTails(); checkCanary(); lengthGovernor(); diffTranscript(); }, 5000);
      send({ type: "guard_ready", site: S.adapter.site });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else { start(); }
})();
