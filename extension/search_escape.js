/**
 * Dhriti Vidura Search-Escape Content Script (D-101).
 *
 * Intercepts searches on Google and YouTube. If the search query matches
 * items you already saved in your Vidura personal library, it surfaces an
 * escape banner: "You already saved this! Watch your saved item instead of falling down the algorithm rabbit hole."
 */

(async function () {
  const url = window.location.href;
  const isGoogle = url.includes("google.") && url.includes("/search");
  const isYouTube = url.includes("youtube.com/results");

  if (!isGoogle && !isYouTube) return;

  const params = new URLSearchParams(window.location.search);
  const query = isGoogle ? params.get("q") : params.get("search_query");

  if (!query || query.trim().length < 2) return;

  // Let background service worker perform the search over bridge
  try {
    chrome.runtime.sendMessage({ type: "vidura_search", query: query.trim() }, response => {
      if (!response || !response.items || response.items.length === 0) return;
      showEscapeBanner(response.items, query.trim());
    });
  } catch (e) {
    // Isolated extension context
  }

  function showEscapeBanner(items, queryStr) {
    if (document.getElementById("dhriti-vidura-escape-banner")) return;

    const topItem = items[0];
    const totalMatches = items.length;

    const banner = document.createElement("div");
    banner.id = "dhriti-vidura-escape-banner";
    banner.setAttribute("style", `
      position: fixed;
      top: 14px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 9999999;
      background: #141726;
      border: 1px solid #8b78f6;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), 0 0 16px rgba(139, 120, 246, 0.35);
      border-radius: 12px;
      padding: 12px 18px;
      display: flex;
      align-items: center;
      gap: 14px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #ffffff;
      font-size: 13.5px;
      max-width: min(680px, 94vw);
      animation: dhritiFadeSlideDown 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    `);

    const styleEl = document.createElement("style");
    styleEl.textContent = `
      @keyframes dhritiFadeSlideDown {
        from { opacity: 0; transform: translate(-50%, -18px); }
        to { opacity: 1; transform: translate(-50%, 0); }
      }
      .dhriti-escape-btn {
        background: #8b78f6;
        color: #ffffff;
        border: none;
        padding: 6px 14px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 12.5px;
        cursor: pointer;
        text-decoration: none;
        white-space: nowrap;
        transition: background 0.15s ease;
      }
      .dhriti-escape-btn:hover {
        background: #9d8df8;
      }
      .dhriti-close-escape {
        background: none;
        border: none;
        color: #8b92b2;
        font-size: 16px;
        cursor: pointer;
        padding: 2px 6px;
      }
      .dhriti-close-escape:hover {
        color: #ffffff;
      }
    `;
    document.head.appendChild(styleEl);

    banner.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="background: rgba(139, 120, 246, 0.2); color: #8b78f6; font-size: 10.5px; font-weight: 700; padding: 2px 7px; border-radius: 4px; border: 1px solid rgba(139, 120, 246, 0.4);">
          VIDURA ESCAPE
        </span>
        <span style="color: #cbd5e1;">
          You already saved <strong>${totalMatches} item${totalMatches > 1 ? 's' : ''}</strong> on this:
          <em style="color: #ffffff;">"${topItem.title.length > 40 ? topItem.title.substring(0, 40) + '...' : topItem.title}"</em>
        </span>
      </div>
      <a href="${topItem.url}" class="dhriti-escape-btn" target="_blank" rel="noopener noreferrer">
        Open Saved ${topItem.kind === 'video' ? 'Video' : 'Item'}
      </a>
      <button type="button" class="dhriti-close-escape" id="btn-close-vidura-escape" title="Dismiss">✕</button>
    `;

    document.body.appendChild(banner);

    document.getElementById("btn-close-vidura-escape").addEventListener("click", () => {
      banner.remove();
    });
  }
})();
