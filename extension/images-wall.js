/*
 * dhriti-e1c · images-wall.js — content ring of the Google Images exile (D-082)
 *
 * Behavior:
 *  1. WALL  — if this page IS a Google Images vertical (images or lens host,
 *             /imghp, /imgres, or /search?...tbm=isch / udm=2): window.stop()
 *             kills every pending load, the DOM is wiped, and a faced wall card
 *             is shown. No blur, no scroll, no thumbnails. "Park this urge"
 *             posts to the parking lot through the service worker.
 *  2. SWEEP — on normal Google pages, every <a href> that points at an Images
 *             entry (the Images tab chip, the homepage "Images" link, inline
 *             Lens links) is removed entirely — same stance as D-032 chip
 *             suppression. A content-blind count is emitted so `dhriti health`
 *             can detect selector drift (D-077).
 *  3. CLICK — capture-phase interception as the last resort: any surviving
 *             Images link is preventDefault-ed and walled instead of navigated.
 *
 * Robustness: matching is href-based (survives class-name redesigns), a 1s
 * re-check covers SPA navigation, and all frames are covered (all_frames: true).
 *
 * [PLUG-IN] points are marked where this meets your existing E1 background.
 */
(() => {
  'use strict';

  const IMG_HOST    = /^(?:images|lens)\.google\./i;
  const GOOGLE_HOST = /(?:^|\.)google\.[a-z]{2,3}(?:\.[a-z]{2,3})?$/i;
  const IMG_PATH    = /^\/(?:imghp|imgres)(?:$|[/?#])/;
  const IMG_HREF    = /(?:images|lens)\.google\.|\/(?:imghp|imgres)|(?:^|[&?])(?:tbm=isch|udm=2)(?:[&#]|$)/i;

  let walled = false;

  function isImagesPage(loc = location) {
    if (IMG_HOST.test(loc.hostname)) return true;
    if (!GOOGLE_HOST.test(loc.hostname)) return false;
    if (IMG_PATH.test(loc.pathname)) return true;
    if (loc.pathname === '/search') {
      const q = loc.search.replace(/^\?/, '');
      return q.split('&').some((kv) => /^(?:tbm=isch|udm=2)$/.test(kv));
    }
    return false;
  }

  function emit(msg) {
    // [PLUG-IN] consumed by background-images.js -> bridge POST /session/event
    try {
      chrome.runtime.sendMessage(msg, () => void chrome.runtime.lastError);
    } catch (_) { /* extension reloading: fail safe, wall still stands */ }
  }

  function wall() {
    if (walled) return;
    walled = true;

    // Halt every pending request and script — the page goes permanently empty.
    try { window.stop(); } catch (_) { /* older engines */ }

    const root = document.documentElement;
    while (root.firstChild) root.removeChild(root.firstChild);

    const style = document.createElement('style');
    style.textContent = `
      html, body { overflow: hidden !important; height: 100%; margin: 0; }
      #dhriti-wall {
        min-height: 100vh; display: flex; align-items: center; justify-content: center;
        background: #101418; color: #e8e6e3;
        font: 16px/1.5 system-ui, "Segoe UI", sans-serif;
      }
      #dhriti-wall .card {
        max-width: 34rem; padding: 2rem 2.25rem;
        border: 1px solid #2a3138; border-radius: 10px; background: #14191f;
      }
      #dhriti-wall h1 { font-size: 1.05rem; margin: 0 0 .75rem; letter-spacing: .02em; }
      #dhriti-wall p  { margin: 0 0 1.25rem; color: #b7bdc4; }
      #dhriti-wall button {
        font: inherit; padding: .5rem 1rem; margin-right: .5rem; border-radius: 6px;
        border: 1px solid #3a424a; background: #1a2128; color: #e8e6e3; cursor: pointer;
      }
      #dhriti-wall button:hover { background: #232b33; }
      #dhriti-wall .why { font-size: .8rem; color: #6d7681; margin-top: 1.5rem; margin-bottom: 0; }
    `;

    const card = document.createElement('div');
    card.id = 'dhriti-wall';
    card.innerHTML = `
      <div class="card">
        <h1>Images vertical — blocked by your contract</h1>
        <p>This entry point is on the blocked list: media grids that lead out to
           unrelated domains. Nothing loads here, and there is nothing to scroll.</p>
        <button id="dhriti-wall-back">Back to search</button>
        <button id="dhriti-wall-park">Park this urge</button>
        <p class="why">Reason: vertical exile (D-082). Recorded: the navigation attempt
           only — your query text is not logged.</p>
      </div>`;
    root.append(style, card);

    document.getElementById('dhriti-wall-back').addEventListener('click', () => {
      if (history.length > 1) history.back();
      else location.replace('https://www.google.com');
    });
    document.getElementById('dhriti-wall-park').addEventListener('click', () => {
      // [PLUG-IN] background-images.js turns this into POST /session/park
      emit({ type: 'dhriti/park', sparkedBy: 'images-vertical' });
    });

    // Content-blind event: attempt only, no query text, no page content (L-4).
    emit({ type: 'dhriti/event', code: 'vertical_wall', target: 'images-vertical', stage: 'read' });
  }

  function sweep() {
    let removed = 0;
    for (const a of document.querySelectorAll('a[href]')) {
      const href = a.getAttribute('href') || '';
      if (IMG_HREF.test(href)) { a.remove(); removed += 1; }
    }
    if (removed) {
      emit({ type: 'dhriti/event', code: 'chip_suppressed', target: 'images-vertical', count: removed });
    }
    return removed;
  }

  function tick() {
    if (isImagesPage()) { wall(); return; }
    if (!walled && GOOGLE_HOST.test(location.hostname)) sweep();
  }

  // Debounced mutation sweep + fixed 1s re-check (SPA navigation, cached pages).
  let debounce = null;
  const schedule = () => {
    if (walled || debounce) return;
    debounce = setTimeout(() => { debounce = null; tick(); }, 300);
  };
  const startObserver = () => {
    const target = document.body || document.documentElement;
    if (target) new MutationObserver(schedule).observe(target, { childList: true, subtree: true });
  };

  if (isImagesPage()) {
    wall();
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { startObserver(); tick(); });
  } else {
    startObserver();
    tick();
  }

  setInterval(tick, 1000);
  addEventListener('popstate', tick);
  addEventListener('hashchange', tick);

  // Last resort: capture-phase click interception on any surviving link.
  document.addEventListener('click', (e) => {
    if (e.defaultPrevented || e.button !== 0 || walled) return;
    const a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (a && IMG_HREF.test(a.getAttribute('href') || '')) {
      e.preventDefault();
      e.stopImmediatePropagation();
      wall();
    }
  }, true);
})();
