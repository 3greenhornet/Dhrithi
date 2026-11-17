/**
 * Dhriti Tactile Dual-Mode Dashboard Controller
 * Handles:
 * 1. Dual-mode transitions (Picture/Quote/Poem vs Focus Dashboard)
 * 2. Solitaire/Minesweeper corner-to-corner wave flip sweep
 * 3. Triple-click gestures (cycle art/poem in Mode 1, return in Mode 2)
 * 4. Pomodoro focus engine (25/5, 50/15, 100/30)
 * 5. Dynamic quote hourly rotation & customizable gallery
 * 6. Live Dhriti Bridge telemetry connector
 * 7. Frosted glass settings manager
 */

(function () {
  'use strict';

  // --- Default Curated Datasets ---
  const DEFAULT_ARTWORKS = [
    {
      id: 'art-1',
      title: 'Water Lilies — Claude Monet',
      url: 'https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?auto=format&fit=crop&w=2000&q=85'
    },
    {
      id: 'art-2',
      title: 'Starry Night — Vincent van Gogh',
      url: 'https://images.unsplash.com/photo-1541701494587-cb58502866ab?auto=format&fit=crop&w=2000&q=85'
    },
    {
      id: 'art-3',
      title: 'The Great Wave — Hokusai',
      url: 'https://images.unsplash.com/photo-1578301978693-85fa9c0320b9?auto=format&fit=crop&w=2000&q=85'
    },
    {
      id: 'art-4',
      title: 'Wanderer Above the Sea of Fog — Friedrich',
      url: 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=2000&q=85'
    },
    {
      id: 'art-5',
      title: 'Golden Horizon — Minimalist Oil',
      url: 'https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=2000&q=85'
    }
  ];

  const DEFAULT_QUOTES = [
    {
      text: "You have power over your mind - not outside events. Realize this, and you will find strength.",
      author: "Marcus Aurelius"
    },
    {
      text: "Simplicity is prerequisite for reliability. Guard your attention with unwavering resolve.",
      author: "Edsger W. Dijkstra"
    },
    {
      text: "It is not that we have a short time to live, but that we waste a lot of it.",
      author: "Seneca"
    },
    {
      text: "Deep work is the ability to focus without distraction on a cognitively demanding task.",
      author: "Cal Newport"
    },
    {
      text: "To work alone is to preserve the sovereign silence where creation takes root.",
      author: "Rainer Maria Rilke"
    },
    {
      text: "One who has conquered the mind has already reached tranquility in cold and heat, joy and sorrow.",
      author: "Bhagavad Gita 6.7"
    },
    {
      text: "Do not wait for extraordinary circumstances to do good action; try to use ordinary situations.",
      author: "Jean Paul Richter"
    }
  ];

  // --- App State ---
  const state = {
    mode: 'picture', // 'picture' | 'dashboard'
    currentArtIndex: 0,
    artworks: [],
    quotes: [],
    currentQuoteIndex: 0,
    bridgeOnline: false,
    bridgeHost: 'http://127.0.0.1:7311',
    pomodoro: {
      mode: 'standard', // 'standard' (25/5), 'extended' (50/15), 'deep' (100/30)
      presets: {
        standard: { focus: 25 * 60, break: 5 * 60 },
        extended: { focus: 50 * 60, break: 15 * 60 },
        deep: { focus: 100 * 60, break: 30 * 60 }
      },
      phase: 'focus', // 'focus' | 'break'
      remaining: 25 * 60,
      isRunning: false,
      timerId: null
    },
    bridgeData: {
      session: {
        active: false,
        intent: 'Deep System Architecture',
        started_at: null,
        duration_minutes: 42
      },
      anchor: {
        next_action: 'Finalize tactile Solitaire flip sweep and link chimes engine',
        blocker: 'None detected',
        updated_at: 'Just now'
      },
      guard: {
        budget_remaining: 15,
        burst_cooldown: 0,
        tier: 'Normal'
      },
      stage: {
        stage_percent: 88,
        audience_percent: 12,
        drift_status: 'Guarded'
      },
      window: {
        curfew: '22:00',
        remaining_hours: 6.5
      }
    }
  };

  // --- DOM Elements Cache ---
  const DOM = {};

  function initDOMCache() {
    DOM.body = document.body;
    DOM.gridBoard = document.getElementById('grid-board');
    DOM.tiles = Array.from(document.querySelectorAll('.tactile-tile'));
    DOM.floatingQuote = document.getElementById('floating-quote');
    DOM.quoteText = document.getElementById('quote-text');
    DOM.quoteAuthor = document.getElementById('quote-author');
    DOM.modeBadge = document.getElementById('mode-badge');
    DOM.statusDot = document.getElementById('status-dot');
    DOM.btnSettings = document.getElementById('btn-settings');
    DOM.settingsOverlay = document.getElementById('settings-overlay');
    DOM.btnCloseSettings = document.getElementById('btn-close-settings');
    DOM.pomoTime = document.getElementById('pomo-time');
    DOM.pomoLabel = document.getElementById('pomo-label');
    DOM.btnPomoToggle = document.getElementById('btn-pomo-toggle');
    DOM.btnPomoReset = document.getElementById('btn-pomo-reset');
    DOM.pomoPresetBtns = document.querySelectorAll('.pomo-preset-btn');
    DOM.artThumbGrid = document.getElementById('art-preset-grid');
    DOM.customArtInput = document.getElementById('custom-art-url');
    DOM.btnAddArt = document.getElementById('btn-add-art');
    DOM.quotesList = document.getElementById('quotes-manager-list');
    DOM.inputNewQuoteText = document.getElementById('new-quote-text');
    DOM.inputNewQuoteAuthor = document.getElementById('new-quote-author');
    DOM.btnAddQuote = document.getElementById('btn-add-quote');
  }

  // --- Local Storage Hydration ---
  function hydrateStorage() {
    try {
      const savedArt = localStorage.getItem('dhriti_artworks');
      state.artworks = savedArt ? JSON.parse(savedArt) : [...DEFAULT_ARTWORKS];
    } catch (e) {
      state.artworks = [...DEFAULT_ARTWORKS];
    }

    try {
      const savedQuotes = localStorage.getItem('dhriti_quotes');
      state.quotes = savedQuotes ? JSON.parse(savedQuotes) : [...DEFAULT_QUOTES];
    } catch (e) {
      state.quotes = [...DEFAULT_QUOTES];
    }

    // Set initial artwork
    applyArtwork(0);

    // Compute hourly quote rotation
    rotateQuoteHourly();
  }

  function applyArtwork(index) {
    if (!state.artworks.length) return;
    state.currentArtIndex = (index + state.artworks.length) % state.artworks.length;
    const art = state.artworks[state.currentArtIndex];
    document.documentElement.style.setProperty('--bg-image', `url('${art.url}')`);
  }

  function rotateQuoteHourly() {
    if (!state.quotes.length) return;
    // Current hour seed ensures all synchronized devices see same quote per hour
    const hourSeed = Math.floor(Date.now() / (1000 * 60 * 60));
    state.currentQuoteIndex = hourSeed % state.quotes.length;
    renderQuote();
  }

  function renderQuote() {
    if (!state.quotes.length || !DOM.quoteText) return;
    const q = state.quotes[state.currentQuoteIndex];
    DOM.quoteText.textContent = `“${q.text}”`;
    DOM.quoteAuthor.textContent = `— ${q.author}`;
  }

  // --- Solitaire / Minesweeper Spatial Wave Flip Sweep ---
  function flipToDashboard(originTile) {
    if (state.mode === 'dashboard') return;
    state.mode = 'dashboard';
    DOM.body.classList.add('mode-dashboard');
    DOM.modeBadge.innerHTML = `<span class="status-dot"></span> Focus Dashboard`;

    // Calculate wave sweep delay using true Euclidean pixel distance from clicked tile center
    const originRect = (originTile || DOM.tiles[0]).getBoundingClientRect();
    const ox = originRect.left + originRect.width / 2;
    const oy = originRect.top + originRect.height / 2;

    DOM.tiles.forEach((tile) => {
      const rect = tile.getBoundingClientRect();
      const tx = rect.left + rect.width / 2;
      const ty = rect.top + rect.height / 2;
      const distance = Math.hypot(tx - ox, ty - oy);
      const delay = Math.round(distance * 0.42);

      setTimeout(() => {
        tile.classList.add('flipped');
        if (window.DhritiAudio) {
          window.DhritiAudio.playCardFlip(1.0 + (distance / 700) * 0.4);
        }
      }, delay);
    });
  }

  function returnToPictureMode(originTile) {
    if (state.mode === 'picture') return;
    state.mode = 'picture';
    DOM.body.classList.remove('mode-dashboard');
    DOM.modeBadge.innerHTML = `<span class="status-dot"></span> Art & Poem Mode`;

    const originRect = (originTile || DOM.tiles[0]).getBoundingClientRect();
    const ox = originRect.left + originRect.width / 2;
    const oy = originRect.top + originRect.height / 2;

    DOM.tiles.forEach((tile) => {
      const rect = tile.getBoundingClientRect();
      const tx = rect.left + rect.width / 2;
      const ty = rect.top + rect.height / 2;
      const distance = Math.hypot(tx - ox, ty - oy);
      const delay = Math.round(distance * 0.35);

      setTimeout(() => {
        tile.classList.remove('flipped');
        if (window.DhritiAudio) {
          window.DhritiAudio.playCardFlip(1.4 - (distance / 700) * 0.35);
        }
      }, delay);
    });

    if (window.DhritiAudio) {
      window.DhritiAudio.playChime(659.25, 0.4);
    }
  }

  // --- Triple Click Detection ---
  let clickCount = 0;
  let clickResetTimer = null;

  function registerTripleClickGesture() {
    window.addEventListener('click', (e) => {
      // Don't trigger if interacting inside settings modal or interactive controls
      if (e.target.closest('#settings-overlay') || 
          e.target.closest('.pomo-controls') || 
          e.target.closest('.drawer-btn') ||
          e.target.closest('button') ||
          e.target.closest('input')) {
        return;
      }

      clickCount++;
      clearTimeout(clickResetTimer);
      clickResetTimer = setTimeout(() => {
        clickCount = 0;
      }, 420);

      if (clickCount >= 3) {
        clickCount = 0;
        handleTripleClick();
      }
    });
  }

  function handleTripleClick() {
    if (state.mode === 'dashboard') {
      // Return gesture from Dashboard to Picture Mode
      returnToPictureMode(DOM.tiles[Math.floor(DOM.tiles.length / 2)]);
    } else {
      // Cycle to new background artwork and trigger fresh poem refresh
      state.currentArtIndex = (state.currentArtIndex + 1) % state.artworks.length;
      applyArtwork(state.currentArtIndex);

      if (window.DhritiChimes && window.DhritiChimes.nextPoemPreset) {
        window.DhritiChimes.nextPoemPreset();
      }

      if (window.DhritiAudio) {
        window.DhritiAudio.playCompletionBell();
      }
    }
  }

  // --- Tile Click Binding ---
  function bindTileClicks() {
    DOM.tiles.forEach((tile) => {
      tile.addEventListener('click', (e) => {
        // In Picture mode: single click triggers the Solitaire wave sweep
        if (state.mode === 'picture') {
          flipToDashboard(tile);
        }
      });
    });
  }

  // --- Pomodoro Engine ---
  function updatePomoDisplay() {
    const min = Math.floor(state.pomodoro.remaining / 60);
    const sec = state.pomodoro.remaining % 60;
    DOM.pomoTime.textContent = `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    DOM.pomoLabel.textContent = state.pomodoro.phase === 'focus' ? 'Focus Interval' : 'Break Recovery';
    DOM.btnPomoToggle.textContent = state.pomodoro.isRunning ? 'Pause' : 'Start';
  }

  function togglePomodoro() {
    if (state.pomodoro.isRunning) {
      clearInterval(state.pomodoro.timerId);
      state.pomodoro.isRunning = false;
      updatePomoDisplay();
    } else {
      state.pomodoro.isRunning = true;
      updatePomoDisplay();
      state.pomodoro.timerId = setInterval(() => {
        if (state.pomodoro.remaining > 0) {
          state.pomodoro.remaining--;
          updatePomoDisplay();
        } else {
          // Timer reached 0
          if (window.DhritiAudio) {
            window.DhritiAudio.playCompletionBell();
          }
          // Switch phase
          if (state.pomodoro.phase === 'focus') {
            state.pomodoro.phase = 'break';
            state.pomodoro.remaining = state.pomodoro.presets[state.pomodoro.mode].break;
          } else {
            state.pomodoro.phase = 'focus';
            state.pomodoro.remaining = state.pomodoro.presets[state.pomodoro.mode].focus;
          }
          updatePomoDisplay();
        }
      }, 1000);
    }
  }

  function resetPomodoro() {
    clearInterval(state.pomodoro.timerId);
    state.pomodoro.isRunning = false;
    state.pomodoro.phase = 'focus';
    state.pomodoro.remaining = state.pomodoro.presets[state.pomodoro.mode].focus;
    updatePomoDisplay();
  }

  function switchPomoPreset(modeKey) {
    if (!state.pomodoro.presets[modeKey]) return;
    state.pomodoro.mode = modeKey;
    DOM.pomoPresetBtns.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.preset === modeKey);
    });
    resetPomodoro();
  }

  function bindPomodoroEvents() {
    DOM.btnPomoToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      togglePomodoro();
    });
    DOM.btnPomoReset.addEventListener('click', (e) => {
      e.stopPropagation();
      resetPomodoro();
    });
    DOM.pomoPresetBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        switchPomoPreset(btn.dataset.preset);
      });
    });
  }

  // --- Dhriti Bridge Telemetry Polling ---
  async function pollBridgeTelemetry() {
    try {
      const res = await fetch(`${state.bridgeHost}/status`, { cache: 'no-store' });
      if (res.ok) {
        const data = await res.json();
        state.bridgeOnline = true;
        DOM.statusDot.classList.remove('offline');
        renderBridgeData(data);
      } else {
        throw new Error('Bridge non-200');
      }
    } catch (err) {
      state.bridgeOnline = false;
      DOM.statusDot.classList.add('offline');
    }
  }

  function renderBridgeData(data) {
    // If telemetry returns active session, resume capsule, or guard data
    if (data.session && data.session.active) {
      const intentEl = document.getElementById('widget-session-intent');
      if (intentEl) intentEl.textContent = data.session.intent || 'Active Focus';
    }
    if (data.capsule) {
      const nextActionEl = document.getElementById('widget-capsule-next');
      if (nextActionEl) nextActionEl.textContent = data.capsule.next_action || 'Resume working copy';
    }
    if (data.guard) {
      const budgetEl = document.getElementById('widget-guard-budget');
      if (budgetEl) budgetEl.textContent = `${data.guard.budget_remaining || 15}m`;
    }
  }

  // --- Settings Modal & Gallery Management ---
  function bindSettingsModal() {
    DOM.btnSettings.addEventListener('click', () => {
      renderGalleryManager();
      renderQuotesManager();
      DOM.settingsOverlay.classList.add('active');
    });

    DOM.btnCloseSettings.addEventListener('click', () => {
      DOM.settingsOverlay.classList.remove('active');
    });

    DOM.settingsOverlay.addEventListener('click', (e) => {
      if (e.target === DOM.settingsOverlay) {
        DOM.settingsOverlay.classList.remove('active');
      }
    });

    // Tab navigation
    const tabs = document.querySelectorAll('.settings-tabs-nav .tab-btn');
    const panes = document.querySelectorAll('.settings-tab-content .tab-pane');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        panes.forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        const target = document.getElementById(tab.dataset.tab);
        if (target) target.classList.add('active');
      });
    });

    // Add Art
    DOM.btnAddArt.addEventListener('click', () => {
      const url = DOM.customArtInput.value.trim();
      if (url) {
        state.artworks.push({
          id: 'custom-' + Date.now(),
          title: 'Custom Artwork',
          url: url
        });
        localStorage.setItem('dhriti_artworks', JSON.stringify(state.artworks));
        DOM.customArtInput.value = '';
        renderGalleryManager();
        applyArtwork(state.artworks.length - 1);
      }
    });

    // Add Quote
    DOM.btnAddQuote.addEventListener('click', () => {
      const text = DOM.inputNewQuoteText.value.trim();
      const author = DOM.inputNewQuoteAuthor.value.trim() || 'Anonymous';
      if (text) {
        state.quotes.push({ text, author });
        localStorage.setItem('dhriti_quotes', JSON.stringify(state.quotes));
        DOM.inputNewQuoteText.value = '';
        DOM.inputNewQuoteAuthor.value = '';
        renderQuotesManager();
        state.currentQuoteIndex = state.quotes.length - 1;
        renderQuote();
      }
    });
  }

  function renderGalleryManager() {
    if (!DOM.artThumbGrid) return;
    DOM.artThumbGrid.innerHTML = '';
    state.artworks.forEach((art, index) => {
      const card = document.createElement('div');
      card.className = `art-thumb ${index === state.currentArtIndex ? 'selected' : ''}`;
      card.style.backgroundImage = `url('${art.url}')`;
      card.innerHTML = `<span class="art-thumb-title">${art.title}</span>`;
      card.addEventListener('click', () => {
        applyArtwork(index);
        renderGalleryManager();
      });
      DOM.artThumbGrid.appendChild(card);
    });
  }

  function renderQuotesManager() {
    if (!DOM.quotesList) return;
    DOM.quotesList.innerHTML = '';
    state.quotes.forEach((q, index) => {
      const row = document.createElement('div');
      row.className = 'item-row';
      row.innerHTML = `
        <div class="item-content">
          <strong>“${q.text}”</strong>
          <div class="item-sub">— ${q.author}</div>
        </div>
        <button class="btn-danger" data-quote-idx="${index}">Delete</button>
      `;
      row.querySelector('.btn-danger').addEventListener('click', (e) => {
        e.stopPropagation();
        if (state.quotes.length <= 1) return; // Keep at least one quote
        state.quotes.splice(index, 1);
        localStorage.setItem('dhriti_quotes', JSON.stringify(state.quotes));
        renderQuotesManager();
        state.currentQuoteIndex = 0;
        renderQuote();
      });
      DOM.quotesList.appendChild(row);
    });
  }

  // --- Interactive Drawers ---
  function bindDrawerActions() {
    const btnPark = document.getElementById('btn-drawer-park');
    const btnLeisure = document.getElementById('btn-drawer-leisure');
    const btnResearch = document.getElementById('btn-drawer-research');

    if (btnPark) {
      btnPark.addEventListener('click', (e) => {
        e.stopPropagation();
        const item = prompt('Park thought/distraction for later:');
        if (item) {
          alert(`Parked in Dhriti Drawer: "${item}"`);
        }
      });
    }

    if (btnLeisure) {
      btnLeisure.addEventListener('click', (e) => {
        e.stopPropagation();
        const mins = prompt('Declare leisure break duration (minutes):', '20');
        if (mins) {
          alert(`Declared leisure: ${mins} minutes protected from drift tracking.`);
        }
      });
    }

    if (btnResearch) {
      btnResearch.addEventListener('click', (e) => {
        e.stopPropagation();
        alert('Research Sandbox active: Cold-State consent enforced.');
      });
    }
  }

  // --- Bootstrapping ---
  function init() {
    initDOMCache();
    hydrateStorage();
    bindTileClicks();
    registerTripleClickGesture();
    bindPomodoroEvents();
    bindSettingsModal();
    bindDrawerActions();

    // Init Chimes Canvas
    if (window.DhritiChimes) {
      window.DhritiChimes.init('chimes-canvas');
    }

    // Telemetry polling loop
    pollBridgeTelemetry();
    setInterval(pollBridgeTelemetry, 5000);

    // Hourly Quote rotation check
    setInterval(rotateQuoteHourly, 60000);
  }

  window.addEventListener('DOMContentLoaded', init);
})();
