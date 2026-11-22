/*
 * Dhriti Wall · images-wall.js (L-9r / Research Doc §26.1 & §10.3).
 *
 * Intelligent Visual Gate & Anti-Springboard Protection:
 *  1. ADULT / 18+ QUERY SUPPRESSION:
 *     - If an adult / explicit / 18+ query is detected:
 *       - On Google Search: completely suppresses the image section/carousels
 *         (#islrg, div[data-attrid="images universal"], .ULSXZd) so no adult thumbnails appear.
 *       - On Google Images vertical: suppresses the image grid and displays a dignified
 *         Safe Guard notice with "Back to Safe Search" and "Park this Urge".
 *  2. NORMAL SEARCH & STUDY IMAGES ALWAYS ALLOWED:
 *     - Normal academic, scientific, coding, and general searches render images normally.
 *     - Never wipes the DOM or shows blank screens for legitimate research.
 *  3. ANTI-SPRINGBOARD BOUNDING (§25.1 / §26.1):
 *     - Even on allowed queries, bounds thumbnail display to 16 items.
 *     - Disables infinite scroll triggers to halt 45-minute dopamine rabbit holes.
 *     - Inserts a clean visual boundary indicator when 16 thumbnails are rendered.
 *  4. SENSITIVE / 18+ ART BLURRING:
 *     - Any sensitive or borderline images receive dynamic CSS blur (filter: blur(28px))
 *       with an unobtrusive review badge.
 */

(() => {
  'use strict';

  const IMG_HOST    = /^(?:images|lens)\.google\./i;
  const GOOGLE_HOST = /(?:^|\.)google\.[a-z]{2,3}(?:\.[a-z]{2,3})?$/i;
  const IMG_PATH    = /^\/(?:imghp|imgres)(?:$|[/?#])/;
  const IMG_VERTICAL_PARAM = /^(?:tbm=isch|udm=2)$/;

  // Fallback offline adult regex matching §26.1 taxonomy
  const LOCAL_ADULT_RX = /\b(?:porn|porno|pornography|xxx|hentai|nsfw|erotic|erotica|sex|sexcam|nude|nudity|naked|milf|boobs|tits|pussy|dick|penis|vagina|anal|blowjob|playboy|onlyfans|rule34|striptease|fetish|bdsm|18\+|adult\s+art|erotic\s+art|nsfw\s+art|ecchi)\b/i;

  let queryChecked = false;
  let isAdultDetected = false;
  let maxAllowedThumbnails = 16;
  let boundaryBannerInserted = false;

  function isImagesVertical(loc = window.location) {
    if (IMG_HOST.test(loc.hostname)) return true;
    if (!GOOGLE_HOST.test(loc.hostname)) return false;
    if (IMG_PATH.test(loc.pathname)) return true;
    if (loc.pathname === '/search') {
      const q = loc.search.replace(/^\?/, '');
      return q.split('&').some((kv) => IMG_VERTICAL_PARAM.test(kv));
    }
    return false;
  }

  function isGoogleSearch(loc = window.location) {
    return GOOGLE_HOST.test(loc.hostname) && loc.pathname === '/search';
  }

  function extractQuery() {
    try {
      const params = new URLSearchParams(window.location.search);
      return (params.get('q') || '').trim();
    } catch (_) {
      return '';
    }
  }

  // --- Dynamic Style Injection ---
  function injectStyles() {
    if (document.getElementById('dhriti-vision-styles')) return;
    const style = document.createElement('style');
    style.id = 'dhriti-vision-styles';
    style.textContent = `
      /* Adult Section Suppression */
      .dhriti-suppress-adult-images {
        display: none !important;
      }
      
      /* Dynamic Sensitive Art Blur */
      .dhriti-blurred-img {
        filter: blur(28px) !important;
        transition: filter 0.35s ease;
        position: relative;
        overflow: hidden;
      }
      .dhriti-blurred-img:hover {
        filter: blur(14px) !important;
      }

      /* Anti-Springboard Visual Boundary */
      .dhriti-visual-boundary {
        grid-column: 1 / -1;
        width: 100%;
        margin: 28px 0;
        padding: 16px 20px;
        background: #12151b;
        border: 1px solid #2a313d;
        border-radius: 10px;
        color: #9da7b3;
        font: 13.5px/1.5 system-ui, -apple-system, sans-serif;
        text-align: center;
        box-sizing: border-box;
      }
      .dhriti-visual-boundary strong {
        color: #e2e8f0;
      }
      .dhriti-visual-boundary .sub {
        font-size: 12px;
        color: #64748b;
        margin-top: 4px;
      }

      /* Dhriti Safe Guard Card */
      #dhriti-safe-guard-card {
        min-height: 80vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #0f1217;
        color: #e2e8f0;
        font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
        padding: 20px;
      }
      #dhriti-safe-guard-card .card {
        max-width: 32rem;
        padding: 2.25rem 2.5rem;
        background: #151921;
        border: 1px solid #28303d;
        border-radius: 12px;
        box-shadow: 0 12px 36px rgba(0,0,0,0.5);
      }
      #dhriti-safe-guard-card .badge {
        display: inline-block;
        padding: 3px 9px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        border-radius: 4px;
        background: #3b2024;
        color: #f87171;
        border: 1px solid #ef444455;
        margin-bottom: 1rem;
      }
      #dhriti-safe-guard-card h1 {
        font-size: 1.15rem;
        font-weight: 600;
        margin: 0 0 0.75rem;
        color: #f1f5f9;
      }
      #dhriti-safe-guard-card p {
        font-size: 0.9rem;
        line-height: 1.55;
        color: #94a3b8;
        margin: 0 0 1.5rem;
      }
      #dhriti-safe-guard-card .btn-group {
        display: flex;
        gap: 10px;
      }
      #dhriti-safe-guard-card button {
        font: inherit;
        font-size: 0.85rem;
        font-weight: 500;
        padding: 0.55rem 1.1rem;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.15s ease;
      }
      #dhriti-safe-guard-card .btn-primary {
        background: #2563eb;
        color: #ffffff;
        border: 1px solid #3b82f6;
      }
      #dhriti-safe-guard-card .btn-primary:hover {
        background: #1d4ed8;
      }
      #dhriti-safe-guard-card .btn-secondary {
        background: #1e2430;
        color: #cbd5e1;
        border: 1px solid #334155;
      }
      #dhriti-safe-guard-card .btn-secondary:hover {
        background: #283142;
      }
    `;
    (document.head || document.documentElement).appendChild(style);
  }

  // --- Adult Section & Grid Suppression ---
  function suppressAdultContent() {
    isAdultDetected = true;

    // 1. If on regular search results, hide the visual image sections completely
    const imageSelectors = [
      '#islrg',
      '.islir',
      'div[data-attrid="images universal"]',
      'div.ULSXZd',
      'div#image-section',
      'g-section-with-header:has(g-scrolling-carousel)',
      'div[jsname="N5160b"]',
      'a[href*="udm=2"]',
      'a[href*="tbm=isch"]'
    ];

    for (const sel of imageSelectors) {
      document.querySelectorAll(sel).forEach(el => {
        el.classList.add('dhriti-suppress-adult-images');
        el.style.setProperty('display', 'none', 'important');
      });
    }

    // 2. If on Google Images vertical (udm=2 or images host), suppress grid and show Safe Guard
    if (isImagesVertical()) {
      const grid = document.querySelector('#islrg') || document.querySelector('[data-lpage]');
      if (grid) {
        grid.style.setProperty('display', 'none', 'important');
      }

      if (!document.getElementById('dhriti-safe-guard-card')) {
        const root = document.querySelector('#rcnt') || document.body || document.documentElement;
        const card = document.createElement('div');
        card.id = 'dhriti-safe-guard-card';
        card.innerHTML = `
          <div class="card">
            <div class="badge">Dhriti Safe Guard · L-9r</div>
            <h1>18+ / Adult Image Grid Suppressed</h1>
            <p>Your search query matches adult or explicit visual media. The visual image grid has been suppressed to protect your study focus and environment.</p>
            <div class="btn-group">
              <button id="dhriti-guard-back" class="btn-primary">Return to Safe Search</button>
              <button id="dhriti-guard-park" class="btn-secondary">Park this Urge</button>
            </div>
          </div>
        `;
        // Insert at top of main container or body
        if (root.firstChild) root.insertBefore(card, root.firstChild);
        else root.appendChild(card);

        document.getElementById('dhriti-guard-back')?.addEventListener('click', () => {
          const q = extractQuery();
          window.location.replace(`https://www.google.com/search?q=${encodeURIComponent(q)}`);
        });

        document.getElementById('dhriti-guard-park')?.addEventListener('click', () => {
          try {
            chrome.runtime.sendMessage({
              type: 'quick_park',
              text: `Suppressed adult visual search: ${extractQuery()}`,
              site: 'google_images'
            });
            window.location.replace('https://www.google.com');
          } catch (_) {
            window.location.replace('https://www.google.com');
          }
        });
      }
    }
  }

  // --- Normal Search: Anti-Springboarding & Thumbnail Bounding ---
  function enforceAntiSpringboard() {
    if (isAdultDetected) return; // Adult suppression takes total precedence

    // Only apply bounded thumbnail cap on image vertical or image grid sections
    const isImg = isImagesVertical();
    if (!isImg) return;

    // Google Images thumbnail container items
    const thumbs = document.querySelectorAll('div.isv-r, div[data-id], .islir');
    if (!thumbs || thumbs.length === 0) return;

    let count = 0;
    let cutoffEl = null;

    thumbs.forEach(t => {
      count++;
      if (count > maxAllowedThumbnails) {
        t.style.setProperty('display', 'none', 'important');
      } else {
        cutoffEl = t;
      }
    });

    // Hide infinite-scroll auto loader triggers
    const autoLoaders = document.querySelectorAll('div[jsaction*="load"], input[value*="Show more"], .mye4qd');
    autoLoaders.forEach(el => {
      el.style.setProperty('display', 'none', 'important');
    });

    // Insert boundary notice once
    if (count > maxAllowedThumbnails && !boundaryBannerInserted && cutoffEl && cutoffEl.parentNode) {
      boundaryBannerInserted = true;
      const banner = document.createElement('div');
      banner.className = 'dhriti-visual-boundary';
      banner.innerHTML = `
        <div><strong>Dhriti Visual Focus Boundary:</strong> 16 thumbnails visible to prevent springboarding.</div>
        <div class="sub">Need more for research? Pivot your study target or return to core focus.</div>
      `;
      cutoffEl.parentNode.insertBefore(banner, cutoffEl.nextSibling);
    }
  }

  // --- Sensitive Art & Borderline Image Blurring ---
  function applyDynamicArtBlur() {
    if (isAdultDetected) return;

    // Scan rendered images on page for suggestive alt text or keywords
    const images = document.querySelectorAll('img:not(.dhriti-processed-img)');
    images.forEach(img => {
      img.classList.add('dhriti-processed-img');
      const alt = (img.getAttribute('alt') || '').toLowerCase();
      const title = (img.getAttribute('title') || '').toLowerCase();
      const text = `${alt} ${title}`;

      if (LOCAL_ADULT_RX.test(text)) {
        img.classList.add('dhriti-blurred-img');
        img.title = '18+ Sensitive Visual (Blurred by Dhriti)';
      }
    });
  }

  // --- Query Evaluation Gate ---
  function evaluateCurrentQuery() {
    const q = extractQuery();
    if (!q) return;

    // Fast local regex check (offline protection)
    if (LOCAL_ADULT_RX.test(q)) {
      suppressAdultContent();
      return;
    }

    // Ask Dhriti Bridge via Background Service Worker
    try {
      chrome.runtime.sendMessage(
        { type: 'check_query', query: q, url: window.location.href },
        (resp) => {
          queryChecked = true;
          if (resp && resp.is_adult === true) {
            suppressAdultContent();
          } else {
            // Normal search and study images are ALLOWED!
            isAdultDetected = false;
            maxAllowedThumbnails = (resp && resp.max_thumbnails) ? resp.max_thumbnails : 16;
            enforceAntiSpringboard();
            applyDynamicArtBlur();
          }
        }
      );
    } catch (_) {
      // Local fallback: allow normal images if no adult regex match
      isAdultDetected = false;
      enforceAntiSpringboard();
    }
  }

  // --- Initializer & Mutation Observer ---
  function init() {
    injectStyles();
    evaluateCurrentQuery();

    // Debounced observer for dynamic Google SPA updates
    let timer = null;
    const observer = new MutationObserver(() => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        if (isAdultDetected) {
          suppressAdultContent();
        } else {
          enforceAntiSpringboard();
          applyDynamicArtBlur();
        }
      }, 250);
    });

    const target = document.body || document.documentElement;
    if (target) {
      observer.observe(target, { childList: true, subtree: true });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Listen for SPA history changes (Google tab clicks)
  window.addEventListener('popstate', () => {
    isAdultDetected = false;
    boundaryBannerInserted = false;
    evaluateCurrentQuery();
  });
})();
