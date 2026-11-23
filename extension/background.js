/**
 * Dhriti Wall — MV3 service worker.
 *
 * Behaviour (Wall Principle — PDF section 2.4):
 *   - Fetches the policy from the local daemon bridge on an alarm.
 *   - Applies declarativeNetRequest redirect rules for blocked domains.
 *   - Redirected navigations land on blocked.html, which shows ONLY the
 *     user's own contract line. No reasons, no copy, no engagement.
 *   - Posts navigation events to the daemon (observation, not judgement).
 *   - No badge text, no notifications, no sounds, nothing to argue with.
 *
 * Fail-safe design:
 *   - No cached policy -> dormant (fail-open outside enforcement).
 *   - Cached policy not expired + enforce=true -> keep enforcing even
 *     if the daemon is unreachable (fail-closed during the window).
 *   - Cached policy EXPIRED -> stop enforcing (a dead daemon can never
 *     lock the browser forever). The TTL is chosen by the daemon.
 *   - Queued events are capped; a dead daemon must not eat memory.
 */

importScripts("config.js");
importScripts("chatguard_background.js");
importScripts("background-images.js");

const RULE_OFFSET = 10000;      // our dynamic rule ids start here
const MAX_RULES = 500;          // DNR dynamic rule cap safety
const QUEUE_KEY = "eventQueue";
const MAX_QUEUE = 200;
const POLICY_KEY = "cachedPolicy";

let currentRuleIds = [];

async function getEffectiveToken() {
  const cfg = self.DHRITI_CONFIG || {};
  try {
    const stored = await chrome.storage.local.get("token");
    if (stored && stored.token) return stored.token;
  } catch (e) { }
  return (cfg.bridgeToken && cfg.bridgeToken !== "PASTE_BRIDGE_TOKEN_HERE") ? cfg.bridgeToken : "";
}

async function fetchPolicy() {
  const cfg = self.DHRITI_CONFIG;
  const token = await getEffectiveToken();
  try {
    const resp = await fetch(cfg.bridgeUrl + "/policy", {
      headers: { "X-Dhriti-Token": token },
      cache: "no-store",
    });
    if (!resp.ok) throw new Error("status " + resp.status);
    const policy = await resp.json();
    await chrome.storage.local.set({ [POLICY_KEY]: policy });
    return policy;
  } catch (err) {
    // Bridge unreachable: fall back to the cached policy if still valid.
    const stored = await chrome.storage.local.get(POLICY_KEY);
    const cached = stored[POLICY_KEY];
    if (cached && cached.expires_at && new Date(cached.expires_at) > new Date()) {
      return cached; // fail-closed inside the TTL window
    }
    return { enforce: false, reason: "bridge unreachable and cache expired" };
  }
}

function ruleFor(domain, idx) {
  // Redirect main-frame navigations to the wall page. Sub-resources are
  // blocked outright so the page cannot half-load around the wall.
  const escaped = domain.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return [
    {
      id: RULE_OFFSET + idx * 2,
      priority: 1,
      action: {
        type: "redirect",
        redirect: { url: chrome.runtime.getURL("blocked.html") },
      },
      condition: {
        urlFilter: "||" + domain + "^",
        resourceTypes: ["main_frame"],
      },
    },
    {
      id: RULE_OFFSET + idx * 2 + 1,
      priority: 1,
      action: { type: "block" },
      condition: {
        urlFilter: "||" + domain + "^",
        resourceTypes: [
          "sub_frame", "script", "image", "stylesheet", "media",
          "xmlhttprequest", "other",
        ],
      },
    },
  ];
}

async function applyPolicy(policy) {
  const wanted = [];
  if (policy.enforce && Array.isArray(policy.blocked_domains)) {
    // Honor the active research pass: temporarily allowed sources are
    // excluded from blocking (bounded allowance, dossier 6.4).
    const researchSources = policy.research_sources || [];
    const isResearchSource = (domain) =>
      researchSources.some((s) => domain === s || domain.endsWith("." + s));
    for (const domain of policy.blocked_domains.slice(0, MAX_RULES)) {
      if (isResearchSource(domain)) continue;
      wanted.push(...ruleFor(domain, wanted.length / 2 | 0));
    }
  }
  const options = { removeRuleIds: currentRuleIds, addRules: wanted };
  await chrome.declarativeNetRequest.updateDynamicRules(options);
  currentRuleIds = wanted.map((r) => r.id);
}

async function postEvent(url, title, tabId) {
  const cfg = self.DHRITI_CONFIG;
  const stored = await chrome.storage.local.get(QUEUE_KEY);
  const queue = stored[QUEUE_KEY] || [];
  queue.push({
    url, title, tabId, ts: new Date().toISOString(),
    ext_version: chrome.runtime.getManifest().version,
  });
  // cap the queue: a dead daemon must not grow memory forever
  const trimmed = queue.slice(-MAX_QUEUE);
  const token = await getEffectiveToken();
  try {
    const resp = await fetch(cfg.bridgeUrl + "/events", {
      method: "POST",
      headers: {
        "X-Dhriti-Token": token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ events: trimmed }),
    });
    if (!resp.ok) throw new Error("status " + resp.status);
    await chrome.storage.local.set({ [QUEUE_KEY]: [] });
  } catch (err) {
    await chrome.storage.local.set({ [QUEUE_KEY]: trimmed });
  }
}

async function postTypedEvent(event) {
  /** Typed events keep their type: surface_suppressed reaches the
   * ledger as itself (D-024), not as a generic navigation. */
  const cfg = self.DHRITI_CONFIG;
  const token = await getEffectiveToken();
  try {
    await fetch(cfg.bridgeUrl + "/events", {
      method: "POST",
      headers: {
        "X-Dhriti-Token": token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        events: [{
          type: event.type,
          url: "https://" + (event.site || "") + "/",
          title: "",
          tabId: -1,
          ts: event.ts || new Date().toISOString(),
          ext_version: chrome.runtime.getManifest().version,
          rule: event.rule || "",
        }],
      }),
    });
  } catch (err) {
    /* typed events are best-effort; the queue is for navigation */
  }
}

let lastEnforce = null;

async function notifyContentScripts(enforce) {
  /** Tell loaded pages the wall flipped (arming or release) so
   * suppression follows the window without a page reload. */
  if (lastEnforce === enforce) return;
  lastEnforce = enforce;
  try {
    const tabs = await chrome.tabs.query({});
    for (const tab of tabs) {
      chrome.tabs.sendMessage(tab.id, {
        type: "enforcement_changed", enforce,
      }, () => void chrome.runtime.lastError);
    }
  } catch (e) { /* no tabs to tell */ }
}

async function closeBlockedTabs(policy) {
  /** Plan Part 4 §1.6 ARMING check 5 (open blocked tabs): when the wall
   * arms, tabs already sitting on blocked domains are closed — the
   * backend can, so it does. Counted, not hidden. */
  if (!policy.enforce || !Array.isArray(policy.blocked_domains)) return;
  let closed = 0;
  for (const domain of policy.blocked_domains.slice(0, 100)) {
    try {
      const tabs = await chrome.tabs.query({
        url: [`*://*.${domain}/*`, `*://${domain}/*`],
      });
      for (const tab of tabs) {
        await chrome.tabs.remove(tab.id);
        closed += 1;
      }
    } catch (e) { /* pattern or permission trouble: skip this domain */ }
  }
  if (closed > 0) {
    await postTypedEvent({
      type: "blocked_tabs_closed", site: "arming", rule: String(closed),
    });
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "BRIDGE_REQ") {
    (async () => {
      const cfg = self.DHRITI_CONFIG || {};
      const url = (cfg.bridgeUrl || "http://127.0.0.1:7311") + (msg.endpoint || "");
      const stored = await chrome.storage.local.get("token");
      const tok = (stored && stored.token) || ((cfg.bridgeToken && cfg.bridgeToken !== "PASTE_BRIDGE_TOKEN_HERE") ? cfg.bridgeToken : "");
      try {
        const resp = await fetch(url, {
          method: msg.method || "GET",
          headers: {
            "Content-Type": "application/json",
            "X-Dhriti-Token": tok,
          },
          body: msg.body ? JSON.stringify(msg.body) : undefined,
        });
        if (!resp.ok) {
          sendResponse(null);
          return;
        }
        const data = await resp.json();
        sendResponse(data);
      } catch (e) {
        sendResponse(null);
      }
    })();
    return true; // async
  }
  if (msg && msg.type === "is_enforcing") {
    chrome.storage.local.get(POLICY_KEY).then((stored) => {
      const cached = stored[POLICY_KEY];
      sendResponse({ enforce: !!(cached && cached.enforce) });
    });
    return true; // async response
  }
  if (msg && (msg.type === "surface_suppressed"
    || msg.type === "surface_rule_stale")) {
    postTypedEvent(msg);
    sendResponse({ ok: true });
    return false;
  }
  if (msg && msg.type === "vidura_search") {
    (async () => {
      const cfg = self.DHRITI_CONFIG || {};
      const token = await getEffectiveToken();
      const q = encodeURIComponent(msg.query || "");
      try {
        const resp = await fetch(`${cfg.bridgeUrl || 'http://127.0.0.1:7311'}/api/vidura/search?q=${q}&limit=5`, {
          headers: { "X-Dhriti-Token": token }
        });
        if (resp.ok) {
          const data = await resp.json();
          sendResponse({ items: data.items || [] });
        } else {
          sendResponse({ items: [] });
        }
      } catch (err) {
        sendResponse({ items: [] });
      }
    })();
    return true; // async response
  }
  if (msg && msg.type === "check_query") {
    (async () => {
      const cfg = self.DHRITI_CONFIG || {};
      const token = await getEffectiveToken();
      try {
        const resp = await fetch(`${cfg.bridgeUrl || 'http://127.0.0.1:7311'}/api/check_query`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Dhriti-Token": token
          },
          body: JSON.stringify({ query: msg.query || "", url: msg.url || "" })
        });
        const activePol = await getActivePolicy();
        const isEnforcing = !!(activePol && activePol.enforce);
        if (resp.ok) {
          const data = await resp.json();
          sendResponse({ ...data, enforcing: isEnforcing });
        } else {
          // Graceful fail-open on transient network error for safe browsing
          sendResponse({ allowed: true, is_adult: false, suppress_image_grid: false, max_thumbnails: isEnforcing ? 16 : 999, enforcing: isEnforcing });
        }
      } catch (err) {
        const activePol = await getActivePolicy().catch(() => null);
        const isEnforcing = !!(activePol && activePol.enforce);
        sendResponse({ allowed: true, is_adult: false, suppress_image_grid: false, max_thumbnails: isEnforcing ? 16 : 999, enforcing: isEnforcing });
      }
    })();
    return true; // async response
  }
  if (msg && msg.type === "classify_image") {
    (async () => {
      const cfg = self.DHRITI_CONFIG || {};
      const token = await getEffectiveToken();
      try {
        const resp = await fetch(`${cfg.bridgeUrl || 'http://127.0.0.1:7311'}/api/vision/classify`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Dhriti-Token": token
          },
          body: JSON.stringify({
            image_b64: msg.image_b64 || "",
            host: msg.host || "",
            metadata: msg.metadata || {}
          })
        });
        if (resp.ok) {
          const data = await resp.json();
          sendResponse(data);
        } else {
          sendResponse({ action: "allow", is_safe: true, is_explicit: false });
        }
      } catch (err) {
        sendResponse({ action: "allow", is_safe: true, is_explicit: false });
      }
    })();
    return true; // async response
  }
  if (msg && msg.type === "get_targets") {
    (async () => {
      const cfg = self.DHRITI_CONFIG || {};
      const token = await getEffectiveToken();
      try {
        const resp = await fetch(`${cfg.bridgeUrl || 'http://127.0.0.1:7311'}/targets`, {
          headers: { "X-Dhriti-Token": token }
        });
        if (resp.ok) {
          const data = await resp.json();
          sendResponse(data);
        } else {
          sendResponse({ ok: false, targets: [] });
        }
      } catch (e) {
        sendResponse({ ok: false, targets: [] });
      }
    })();
    return true;
  }
  if (msg && msg.type === "quick_park") {
    (async () => {
      const cfg = self.DHRITI_CONFIG || {};
      const token = await getEffectiveToken();
      try {
        const resp = await fetch(`${cfg.bridgeUrl || 'http://127.0.0.1:7311'}/guard/park`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Dhriti-Token": token },
          body: JSON.stringify({
            text: msg.text || "",
            site: msg.site || "browser_overlay",
            thread_id: "sticky_note",
            prompt_hash: "overlay_" + Date.now()
          })
        });
        sendResponse({ ok: resp.ok });
      } catch (e) {
        sendResponse({ ok: false });
      }
    })();
    return true;
  }
  if (msg && msg.type === "claim_target") {
    (async () => {
      const cfg = self.DHRITI_CONFIG || {};
      const token = await getEffectiveToken();
      try {
        const resp = await fetch(`${cfg.bridgeUrl || 'http://127.0.0.1:7311'}/targets/claim`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Dhriti-Token": token },
          body: JSON.stringify({ target_id: msg.target_id, label: msg.label })
        });
        sendResponse({ ok: resp.ok });
      } catch (e) {
        sendResponse({ ok: false });
      }
    })();
    return true;
  }
  return false;
});

// --- Private Window Auto-Closure (Requirement 5 & D2) ---
if (chrome.windows && chrome.windows.onCreated) {
  chrome.windows.onCreated.addListener(async (win) => {
    if (win.incognito) {
      // Only close incognito when active enforcement is armed (fail-open when dormant!)
      const pol = await getActivePolicy().catch(() => null);
      if (!pol || !pol.enforce) return;
      try {
        await chrome.windows.remove(win.id);
        postTypedEvent({ type: "private_window_closed", site: "browser", rule: "incognito" });
      } catch (e) {
        console.warn("Private window auto-closed notice:", e);
      }
    }
  });
}

// --- Omnibox Keyword 'v' (Vidura Personal Search D-100) ---
if (chrome.omnibox) {
  chrome.omnibox.onInputChanged.addListener(async (text, suggest) => {
    const query = (text || "").trim();
    if (!query) return;
    const cfg = self.DHRITI_CONFIG || {};
    const token = await getEffectiveToken();
    try {
      const res = await fetch(`${cfg.bridgeUrl || 'http://127.0.0.1:7311'}/api/vidura/search?q=${encodeURIComponent(query)}&limit=6`, {
        headers: { "X-Dhriti-Token": token }
      });
      if (res.ok) {
        const data = await res.json();
        const suggestions = (data.items || []).map(item => {
          const cleanTitle = (item.title || "").replace(/[<>&]/g, "");
          const domain = item.facet_domain || "general";
          const form = item.facet_form || item.kind || "video";
          return {
            content: item.url,
            description: `<match>${cleanTitle}</match> <dim>(${form} | ${domain})</dim>`
          };
        });
        suggest(suggestions);
      }
    } catch (e) { }
  });

  chrome.omnibox.onInputEntered.addListener((text, disposition) => {
    let targetUrl = (text || "").trim();
    if (!targetUrl.startsWith("http://") && !targetUrl.startsWith("https://")) {
      const cfg = self.DHRITI_CONFIG || {};
      targetUrl = `${cfg.bridgeUrl || 'http://127.0.0.1:7311'}/dashboard/?q=${encodeURIComponent(targetUrl)}`;
    }
    if (disposition === "currentTab") {
      chrome.tabs.update({ url: targetUrl });
    } else {
      chrome.tabs.create({ url: targetUrl });
    }
  });
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.url || changeInfo.title) {
    postEvent(changeInfo.url || "", changeInfo.title || "", tabId);
  }
});

chrome.runtime.onInstalled.addListener(() => syncAndApply());
chrome.runtime.onStartup.addListener(() => syncAndApply());

async function syncAndApply() {
  const policy = await fetchPolicy();
  await applyPolicy(policy);
  // A tiny action badge shows ONLY whether the wall is up (state, not
  // judgement). No counts, no streaks, no shame colors.
  try {
    await chrome.action.setBadgeText({
      text: policy.enforce ? "D" : "",
    });
  } catch (e) {
    /* action API optional */
  }
  await closeBlockedTabs(policy);
  await notifyContentScripts(!!policy.enforce);
}

chrome.alarms.create("dhriti-sync", {
  periodInMinutes: Math.max(0.5, (self.DHRITI_CONFIG.pollSeconds || 30) / 60),
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "dhriti-sync") syncAndApply();
});

syncAndApply();
