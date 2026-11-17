/*
 * chatguard_background.js -- Dhriti Guard Kit, MV3 service worker.
 *
 * Responsibilities:
 *   - Policy/state loop: poll the bridge (X-Dhriti-Token), TTL-gated. On
 *     TTL lapse the guard degrades to LOCAL DETERMINISTIC governors only
 *     (burst toll + last-known budgets). It never bricks the chat and
 *     never silently opens (matches D-062 fail-safe philosophy).
 *   - Rate governor corroboration: webRequest observation (onBeforeRequest
 *     URL counts only -- MV3 cannot block dynamically; the DOM is the
 *     enforcement surface, the network is the sensor).
 *   - Message router: content script <-> bridge.
 *   - Arming gate for the optional sidecar (L-9): probe /health, arm, and
 *     record the consent event via /guard/sidecar_armed.
 */

(() => {
  "use strict";

  const BRIDGE_URL = (self.DHRITI_CONFIG && self.DHRITI_CONFIG.bridgeUrl) || "http://127.0.0.1:7311";
  const POLICY_TTL_MS = 5 * 60 * 1000;         // match bridge.policy_ttl_minutes
  const CHAT_ENDPOINTS = [
    /chatgpt\.com\/backend-api\/conversation/,
    /chat\.openai\.com\/backend-api\/conversation/,
    /gemini\.google\.com.*\/StreamGenerate/,
    /chat\.deepseek\.com\/api\/v0\/chat\/completion/,
    /claude\.ai\/api\/organizations\/.*\/completion/,
  ];

  const st = {
    token: "",
    policy: null,            // {mode, prompt_budget_limit, length_limit_chars}
    policyTs: 0,
    sidecar: { url: "http://127.0.0.1:8765", token: "", armed: false },
    localSends: [],          // local deterministic burst counters
    blind: {},               // site -> last probe ok
  };

  const BURST = { windowMs: 60000 * 10, threshold: 3, tollS: 10 };

  chrome.storage.local.get(["token", "sidecarToken", "sidecarUrl"], (g) => {
    st.token = g.token || (self.DHRITI_CONFIG && self.DHRITI_CONFIG.bridgeToken) || "";
    st.sidecar.token = g.sidecarToken || st.token || "";
    if (g.sidecarUrl) st.sidecar.url = g.sidecarUrl;
    pollPolicy();
  });
  chrome.alarms.create("guard-policy", { periodInMinutes: 1 });
  chrome.alarms.onAlarm.addListener((a) => {
    if (a.name === "guard-policy") pollPolicy();
  });

  async function bridge(path, body) {
    const res = await fetch(BRIDGE_URL + path, {
      method: body ? "POST" : "GET",
      headers: { "Content-Type": "application/json",
                 "X-Dhriti-Token": st.token },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error("bridge " + res.status);
    return await res.json();
  }

  function ttlAlive() { return st.policy && (Date.now() - st.policyTs) < POLICY_TTL_MS; }

  async function pollPolicy() {
    try {
      const snap = await bridge("/guard/state");
      st.policy = snap;
      st.policyTs = Date.now();
    } catch (e) {
      // daemon dead: keep last policy as LOCAL deterministic rules; the
      // content decisions (in_scope) are unavailable -> structural only.
      if (!st.policy) st.policy = { mode: "advisory", degraded: true };
      else st.policy.degraded = true;
    }
  }

  function burstToll() {
    const now = Date.now();
    st.localSends = st.localSends.filter((t) => now - t <= BURST.windowMs);
    return st.localSends.length >= BURST.threshold ? BURST.tollS : 0;
  }

  // webRequest observation: URL counts only (no bodies; MV3 cannot block)
  try {
    chrome.webRequest.onBeforeRequest.addListener(
      (det) => {
        if (det.initiator && det.initiator.startsWith("http")) {
          st.localSends.push(Date.now());
        }
      },
      { urls: ["https://chatgpt.com/*", "https://gemini.google.com/*",
               "https://chat.deepseek.com/*", "https://claude.ai/*"],
        types: ["xmlhttprequest"] },
      [] // non-blocking by definition in MV3
    );
  } catch (e) { /* webRequest unavailable: DOM counters still work */ }

  // sidecar classification (optional; text goes loopback only)
  async function sidecarVerdict(promptText, anchors, recent) {
    if (!st.sidecar.armed || !st.sidecar.token) return null;
    try {
      const res = await fetch(st.sidecar.url + "/verdict", {
        method: "POST",
        headers: { "Content-Type": "application/json",
                   "X-Dhriti-Token": st.sidecar.token },
        body: JSON.stringify({ prompt: promptText, anchors, recent }),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch (e) { return null; }
  }

  // ------------------------------------------------------------------
  // message router
  // ------------------------------------------------------------------
  chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
    (async () => {
      switch (msg.type) {
        case "guard_ready":
        case "guard_probe": {
          st.blind[msg.site] = !!msg.ok;
          try { await bridge("/guard/adapter_health",
            { site: msg.site, ok: !!msg.ok, missing: msg.missing || [],
              detail: msg.detail || "" }); } catch (e) {}
          reply({ ok: true });
          break;
        }
        case "guard_canary_missing": {
          try { await bridge("/guard/adapter_health",
            { site: msg.site, ok: true, canary_missing: true,
              detail: msg.detail || "" }); } catch (e) {}
          reply({ ok: true });
          break;
        }
        case "guard_send": {
          let out = { action: "send", toll_seconds: 0, card_lines: [] };
          try {
            let verdict = null;
            if (st.sidecar.armed && msg.prompt_text) {
              const anchors = (st.policy && st.policy.anchors) || [];
              verdict = await sidecarVerdict(msg.prompt_text, anchors, st.recentPrompts || []);
            }
            out = await bridge("/guard/send_event", {
              site: msg.site, thread_id: msg.thread_id,
              prompt_hash: msg.prompt_hash,
              sidecar_verdict: verdict });
            st.localSends.push(Date.now());
            if (msg.prompt_text) {
              st.recentPrompts = st.recentPrompts || [];
              st.recentPrompts.push(msg.prompt_text);
              if (st.recentPrompts.length > 10) st.recentPrompts.shift();
            }
          } catch (e) {
            // LOCAL FALLBACK (daemon dead): deterministic burst governor only
            const toll = burstToll();
            out = toll ? { action: "hold_toll", toll_seconds: toll,
                           card_lines: ["Burst toll active (local rule).",
                                        "Park, take the toll, or cancel."] }
                       : { action: "send" };
          }
          reply(out);
          break;
        }
        case "guard_toll_paid": {
          try { reply(await bridge("/guard/toll_paid",
            { site: msg.site, thread_id: msg.thread_id,
              prompt_hash: msg.prompt_hash })); }
          catch (e) { reply({ action: "send" }); }
          break;
        }
        case "guard_park": {
          try { reply(await bridge("/guard/park", msg)); }
          catch (e) { reply({ parked: false }); }
          break;
        }
        case "guard_learn_safe": {
          try { reply(await bridge("/guard/learn_safe", msg)); }
          catch (e) { reply({ ok: false }); }
          break;
        }
        case "guard_thread_open": {
          try { reply(await bridge("/guard/thread_open", msg)); }
          catch (e) {
            const budget = PIVOT_BUDGET_LOCAL[st.policy?.mode] ?? null;
            reply({ allowed: budget === null ? true : budget > 0,
                    reason: budget === null ? "unlimited" : "pivot_budget" });
          }
          break;
        }
        case "guard_leak": {
          // unapproved send path: collapse what follows (soft, reviewable)
          const degraded = !ttlAlive();
          reply({ collapse: st.policy?.mode !== "advisory",
                  reason: degraded ? "degraded_local" : "unapproved_send" });
          break;
        }
        case "guard_response_hidden": {
          try { await bridge("/guard/send_event",
            { site: msg.site, thread_id: msg.thread_id,
              kind: "response_hidden", prompt_hash: msg.prompt_hash || "" }); }
          catch (e) {}
          reply({ ok: true });
          break;
        }
        case "guard_reveal_request": {
          // Reveal is a COLD act; hot mode denies with one factual line.
          reply({ allow: false,
                  card_line: "Reveal at checkpoint or day_close." });
          break;
        }
        case "guard_override": {
          try { await bridge("/guard/override", msg); } catch (e) {}
          reply({ ok: true });
          break;
        }
        case "guard_sidecar_arm": {
          const ok = await probeSidecar();
          try { await bridge("/guard/sidecar_armed", { ok, backend: "probe" }); }
          catch (e) {}
          st.sidecar.armed = ok;
          reply({ armed: ok });
          break;
        }
        default: reply({});
      }
    })();
    return true;   // async reply
  });

  const PIVOT_BUDGET_LOCAL = { full_lock: 0, reduced_lock: 1,
                               checkpoint: null, advisory: null };

  async function probeSidecar() {
    try {
      const res = await fetch(st.sidecar.url + "/health", {
        headers: { "X-Dhriti-Token": st.sidecar.token } });
      if (!res.ok) return false;
      const j = await res.json();
      return !!(j && j.ok);
    } catch (e) { return false; }
  }
})();
