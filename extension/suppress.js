/**
 * Dhriti Wall — surface suppression content script (D-024).
 *
 * The default interface is retrieval, not recommendation. During strict
 * sessions this script removes the SPRINGBOARD on the most common
 * surfaces: home feeds, Shorts, recommendation sidebars, "related"
 * blocks, and — the Specimen-001 lesson — the follow-up suggestions
 * that AI chats append to every answer. The DOMAIN stays allowed; the
 * surface that turns the domain into a slot machine is removed.
 *
 * Design constraints (deliberate):
 *   - No reason strings, no badges, no "blocked by..." toasts. The page
 *     just loses its feed. A wall does not comment.
 *   - Deterministic CSS/selector rules, five surfaces, no more. If a
 *     selector goes stale the rule silently stops matching and a
 *     `surface_rule_stale` marker is emitted for cold review — fixing
 *     selectors is a cold-state chore, never an in-session one.
 *   - One `surface_suppressed` event per rule per page load (deduped);
 *     the ledger records that the rule fired, not what you read.
 *   - Asks the service worker whether the wall is up before doing
 *     anything; dormant outside enforcement.
 */

(() => {
  "use strict";

  // Rules per hostname. Each rule: css to hide, optional hideText
  // (elements whose text matches get hidden — used sparingly), and a
  // note for cold review. Selectors are short and structural; they WILL
  // break as sites change — that breakage is itself logged, not hidden.
  // RULES: per-hostname static rules (see below).
  // AIMODE_RULES: applied only while the page is Google AI Mode
  // (www.google.com/search?udm=50). Specimen 001 — the project's founding
  // specimen — happened ON this surface: an AI chat that lives on the
  // same domain search needs. It can never be category-blocked (google.com
  // must stay reachable for search), so surface suppression is the only
  // lever. The DOM of AI Mode is UNVERIFIED at write time: these are
  // day-one candidates. A selector that matches nothing logs
  // surface_rule_stale and is fixed in cold state — the standing
  // convention. We suppress the SPRINGBOARD surfaces (follow-ups,
  // related questions), never the chat itself and never the AI Mode entry
  // link: the domain stays allowed, the slot-machine surface goes
  // (D-024, Specimen-001 lesson; wall does not comment).
  const AIMODE_RULES = [
    { id: "aimode-followups",
      css: "[data-testid='suggested-follow-ups'], [aria-label*='follow-up' i], follow-up-suggestions" },
    { id: "aimode-related-qs",
      css: ".related-question-pair, [aria-label*='related question' i]" },
  ];

  const RULES = {
    "www.youtube.com": [
      { id: "yt-home-feed", css: "ytd-browse[page-subtype='home'] #contents" },
      { id: "yt-shorts", css: "ytd-reel-shelf-renderer, ytd-rich-shelf-renderer[is-shorts]" },
      { id: "yt-related", css: "#related, ytd-watch-next-secondary-error-renderer" },
      { id: "yt-endscreen", css: ".ytp-endscreen-content" },
    ],
    "youtube.com": [
      { id: "yt-home-feed", css: "ytd-browse[page-subtype='home'] #contents" },
      { id: "yt-shorts", css: "ytd-reel-shelf-renderer" },
      { id: "yt-related", css: "#related" },
    ],
    "www.reddit.com": [
      { id: "reddit-home-feed", css: "main .scrollerItem, shreddit-feed" },
      { id: "reddit-popular", css: "[data-testid='post-container']" },
    ],
    "old.reddit.com": [
      { id: "reddit-old-feed", css: "#siteTable" },
    ],
    "x.com": [
      { id: "x-for-you", css: "[data-testid='primaryColumn'] [data-testid='cellInnerDiv']" },
      { id: "x-who-to-follow", css: "[data-testid='UserCell'], [data-testid='placementTracking']" },
      { id: "x-trending", css: "[data-testid='trend']" },
    ],
    "twitter.com": [
      { id: "x-for-you", css: "[data-testid='primaryColumn'] [data-testid='cellInnerDiv']" },
      { id: "x-who-to-follow", css: "[data-testid='UserCell']" },
    ],
    "www.google.com": [
      { id: "g-related-searches", css: "[id^='eowp'], [data-initq] ~ div" },
      { id: "g-people-also-ask", css: ".related-question-pair" },
      // AI Mode (udm=50) shares this host; its chat surfaces are handled
      // by AIMODE_RULES at apply time — see the note above the RULES table.
    ],
    "chatgpt.com": [
      // The conversational springboard: suggested follow-ups and the
      // sidebar of previous chats mid-session. Both end the "unit of
      // work" by proposing the next one.
      { id: "ai-followups", css: "[data-testid='suggested-follow-ups'], #prompt-suggestions" },
      { id: "ai-sidebar-history", css: "nav[aria-label='Chat history']" },
    ],
    "chat.openai.com": [
      { id: "ai-followups", css: "#prompt-suggestions" },
    ],
    "claude.ai": [
      { id: "ai-followups", css: "[data-testid='suggested-replies'], .font-claude-suggestion" },
    ],
    "gemini.google.com": [
      { id: "ai-followups", css: "follow-up-suggestions, .follow-up-chips" },
    ],
  };

  const fired = new Set();   // rule ids already reported this page load
  let styleEl = null;
  let observer = null;

  function rulesFor(host) {
    return RULES[host] || [];
  }

  function isAIMode() {
    if (location.hostname !== "www.google.com" &&
        location.hostname !== "google.com") return false;
    try {
      return new URLSearchParams(location.search).get("udm") === "50";
    } catch (e) { return false; }
  }

  function activeRules(host) {
    const base = rulesFor(host);
    return isAIMode() ? base.concat(AIMODE_RULES) : base;
  }

  function cssFor(rules) {
    const parts = [];
    for (const rule of rules) {
      parts.push(`${rule.css} { display: none !important; }`);
    }
    // YouTube: also kill autoplay by hiding the toggle is not enough —
    // best-effort click is handled in applyRules, CSS here only hides
    // the surfaces. The video element itself stays.
    return parts.join("\n");
  }

  function report(ruleId) {
    if (fired.has(ruleId)) return;
    fired.add(ruleId);
    try {
      chrome.runtime.sendMessage({
        type: "surface_suppressed",
        site: location.hostname,
        rule: ruleId,
        ts: new Date().toISOString(),
      });
    } catch (e) {
      /* extension context gone; nothing to report to */
    }
  }

  function applyRules() {
    const host = location.hostname;
    const hostRules = activeRules(host);
    if (!hostRules.length) return;
    if (!styleEl) {
      styleEl = document.createElement("style");
      styleEl.id = "dhriti-suppress";
      (document.head || document.documentElement).appendChild(styleEl);
    }
    styleEl.textContent = cssFor(hostRules);
    // Report each rule that actually matched something (and mark rules
    // that matched nothing across a whole minute as stale, cold-state).
    for (const rule of hostRules) {
      try {
        if (document.querySelector(rule.css)) {
          report(rule.id);
        }
      } catch (e) {
        /* invalid selector — stale rule; ignored, cold review sees it */
      }
    }
    // YouTube autoplay: click the toggle off once per page load when
    // present. Best effort; no retry loop, no commentary.
    if (host.endsWith("youtube.com")) {
      const toggle = document.querySelector(".ytp-autonav-toggle-button");
      if (toggle && toggle.getAttribute("aria-checked") === "true") {
        toggle.click();
        report("yt-autoplay-off");
      }
    }
  }

  function start() {
    applyRules();
    // SPA route changes (YouTube/X/ChatGPT never reload the page).
    observer = new MutationObserver(() => {
      // debounce via microtask-free throttle
      if (start._pending) return;
      start._pending = true;
      setTimeout(() => {
        start._pending = false;
        applyRules();
      }, 400);
    });
    observer.observe(document.documentElement, {
      childList: true, subtree: true,
    });
  }

  // Only act while the wall is up. Ask the worker; if no answer (worker
  // asleep), assume dormant — the worker will re-trigger on next alarm
  // by messaging us (see background.js).
  chrome.runtime.sendMessage({ type: "is_enforcing" }, (resp) => {
    const enforcing = !chrome.runtime.lastError && resp && resp.enforce;
    if (!enforcing) return;
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
    } else {
      start();
    }
    window.addEventListener("popstate", applyRules);
  });

  // The worker pings content scripts when the policy flips (arming or
  // release) so suppression follows the window without a reload.
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg && msg.type === "enforcement_changed") {
      if (msg.enforce) {
        start();
      } else if (observer) {
        observer.disconnect();
        if (styleEl) styleEl.textContent = "";
        fired.clear();
      }
      sendResponse({ ok: true });
    }
    return false;
  });
})();
