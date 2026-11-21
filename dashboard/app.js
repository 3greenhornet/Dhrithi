/**
 * Dhriti Tactile Dual-Mode Focus Dashboard & App Shell Controller (v0.7.0+)
 * Handles:
 * 1. Dual-mode transitions (Art, Quote & Suspended Poem vs Executive App Shell)
 * 2. Solitaire wave sweep on tactile Lego blocks
 * 3. Navigation across views (The Desk, Focus, Tasks, Completed, Topics, Parking, Mirror, Backlog, Guard, Stats, Ledger, Settings)
 * 4. Procedural Pomodoro Engine with procedural alarms and ambient noise generator
 * 5. Life Mirror floating thought bubbles (D-092) with uniform random selection & silent expiry
 * 6. Dynamic Backlog & Pick-Your-Poison task balancer (D-093)
 * 7. Live Topic-Time stacked bar distributions (D-091 / L-11)
 * 8. Decompression Zone manager & Daily Lockdown controller (L-6 Asymmetric consent)
 * 9. Dark Purple & Light Cyan theme toggles with live underlay dials
 */

(function () {
  'use strict';

  // --- Curated Artwork Sets ---
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

  // --- Curated Quotes ---
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
    }
  ];

  // --- Declared Life Alternatives (D-092) ---
  const DEFAULT_LIFE_ALTS = [
    { id: 'life-1', label: 'Back exercises — min 10m', category: 'physical', duration: 10 },
    { id: 'life-2', label: 'Walk around neighborhood — 15m', category: 'nature', duration: 15 },
    { id: 'life-3', label: 'Acoustic guitar practice — 20m', category: 'offline_craft', duration: 20 },
    { id: 'life-4', label: 'Deep breathing & posture reset — 5m', category: 'rest', duration: 5 },
    { id: 'life-5', label: 'Read physical book chapter — 15m', category: 'reading', duration: 15 }
  ];

  // --- Backlog Repository (D-093) ---
  const DEFAULT_BACKLOG = [
    { id: 'task-101', title: 'Write zero-sample synthesized chime tests', units: 1.0, tier: 'medium' },
    { id: 'task-102', title: 'Verify FTS5 virtual table synchronization', units: 2.0, tier: 'hard' },
    { id: 'task-103', title: 'Review topic tokenization stopwords dictionary', units: 0.5, tier: 'light' },
    { id: 'task-104', title: 'Refactor bridge decompression strike counter', units: 1.0, tier: 'medium' },
    { id: 'task-105', title: 'Implement Vidura hierarchical topic tree tests', units: 2.0, tier: 'hard' },
    { id: 'task-106', title: 'Format daily topic-time stacked bar renderer', units: 0.5, tier: 'light' },
    { id: 'task-107', title: 'Full compiler optimization pass on audit chain', units: 3.0, tier: 'challenging' }
  ];

  // --- App State ---
  const state = {
    mode: 'picture', // 'picture' | 'dashboard'
    currentView: 'desk',
    theme: 'dark', // 'dark' | 'light'
    underlay: {
      brightness: parseInt(localStorage.getItem('dhriti_bg_brightness') || '100', 10),
      blur: parseInt(localStorage.getItem('dhriti_bg_blur') || '0', 10),
      opacity: parseInt(localStorage.getItem('dhriti_bg_opacity') || '100', 10)
    },
    currentArtIndex: 0,
    artworks: DEFAULT_ARTWORKS,
    localArtworks: [],
    artSets: [],
    activeSetId: localStorage.getItem('dhriti_active_set_id') || 'set-curated-museum',
    activeArtId: localStorage.getItem('dhriti_active_art') || 'art-1',
    inspectedSetId: null,
    pendingUploadFiles: [],
    cycleUserUploads: localStorage.getItem('dhriti_cycle_user_uploads') === 'true',
    quotes: DEFAULT_QUOTES,
    currentQuoteIndex: 0,
    lifeAlts: DEFAULT_LIFE_ALTS,
    backlog: DEFAULT_BACKLOG,
    activeTasks: [
      { id: 'task-1', title: 'Complete tactile Lego projection & Solitaire flip', units: 1.0, proof: 'machine_check', done: true },
      { id: 'task-2', title: 'Modernize App Shell & Executive dark theme', units: 2.0, proof: 'pytest_pass', done: true },
      { id: 'task-3', title: 'Wire procedural alarms and Life Mirror thought bubbles', units: 1.0, proof: 'browser_verify', done: false }
    ],
    completedTasks: [
      { id: 'task-0', title: 'Implement separate Vidura SQLite storage and topic tree', proof: 'sha256:4f8e...ba12', timestamp: '11:20' },
      { id: 'task-prev', title: 'Commit and push prior state before major additions', proof: 'git:658420a', timestamp: '12:45' }
    ],
    parkingItems: [
      { id: 'park-1', text: 'Consider PyTorch WASM inference for local text embeddings', age_days: 1, type: 'spark' },
      { id: 'park-2', text: 'Explore Japanese Pythagorean scale frequencies for chimes', age_days: 0, type: 'spark' }
    ],
    topicTime: [
      { domain: 'github.com', category: 'Stage (Code & Docs)', duration_min: 140, is_stage: true },
      { domain: 'localhost:7311', category: 'Stage (Dashboard & Bridge)', duration_min: 80, is_stage: true },
      { domain: 'google.com/search', category: 'Stage (Docs Query)', duration_min: 25, is_stage: true },
      { domain: 'random-blog.org', category: 'Audience (Drift Attempt)', duration_min: 12, is_stage: false }
    ],
    decompression: {
      active: false,
      remaining_min: 90,
      strikes: 0,
      max_strikes: 4
    },
    pomodoro: {
      mode: 'standard', // 'standard' | 'extended' | 'deep'
      presets: {
        standard: { focus: 25 * 60, break: 5 * 60 },
        extended: { focus: 50 * 60, break: 15 * 60 },
        deep: { focus: 100 * 60, break: 30 * 60 }
      },
      phase: 'focus',
      remaining: 25 * 60,
      isRunning: false,
      timerId: null,
      noisePlaying: false,
      alarmSound: 'singing_bowl'
    },
    bubbleTimerId: null
  };

  // --- DOM Elements Cache ---
  const DOM = {};

  function initDOM() {
    DOM.body = document.body;
    DOM.heroViewport = document.getElementById('hero-viewport');
    DOM.appShell = document.getElementById('app-shell');
    DOM.gridBoard = document.getElementById('grid-board');
    DOM.tiles = Array.from(document.querySelectorAll('.tactile-tile'));
    DOM.floatingQuote = document.getElementById('floating-quote');
    DOM.quoteText = document.getElementById('quote-text');
    DOM.quoteAuthor = document.getElementById('quote-author');
    DOM.modeBadge = document.getElementById('mode-badge');
    DOM.modeBadgeText = document.getElementById('mode-badge-text');
    DOM.btnToggleMode = document.getElementById('btn-toggle-dashboard-mode');
    DOM.btnToggleText = document.getElementById('btn-toggle-text');
    DOM.btnNavArtMode = document.getElementById('btn-nav-art-mode');
    DOM.sidebarBrand = document.querySelector('.sidebar-brand');
    DOM.btnThemeToggle = document.getElementById('btn-theme-toggle');
    DOM.themeIconDark = document.getElementById('theme-icon-dark');
    DOM.themeIconLight = document.getElementById('theme-icon-light');
    DOM.bubbleLayer = document.getElementById('bubble-layer');
    DOM.miniTimerPill = document.getElementById('mini-timer-pill');
    DOM.miniTimerDisplay = document.getElementById('mini-timer-display');
    DOM.headerPomoPill = document.getElementById('header-pomo-pill');
    DOM.headerPomoDot = document.getElementById('header-pomo-dot');
    DOM.headerPomoPhase = document.getElementById('header-pomo-phase');
    DOM.headerPomoTime = document.getElementById('header-pomo-time');
    DOM.headerPomoToggle = document.getElementById('header-pomo-toggle');
    DOM.headerPomoPlayIcon = document.getElementById('header-pomo-play-icon');
    DOM.headerPomoPauseIcon = document.getElementById('header-pomo-pause-icon');
    DOM.btnReturnArt = document.getElementById('btn-return-art');
    DOM.navItems = Array.from(document.querySelectorAll('.nav-item'));
    DOM.shellViews = Array.from(document.querySelectorAll('.shell-view'));

    // Desk elements
    DOM.deskTopicBars = document.getElementById('desk-topic-bars');
    DOM.donutCanvas = document.getElementById('donut-stage-canvas');
    DOM.quickParkInput = document.getElementById('quick-park-input');
    DOM.btnQuickPark = document.getElementById('btn-quick-park');
    DOM.quickParkFeedback = document.getElementById('quick-park-feedback');

    // Focus elements
    DOM.focusBigTimer = document.getElementById('focus-big-timer');
    DOM.btnFocusStart = document.getElementById('btn-focus-start');
    DOM.btnFocusReset = document.getElementById('btn-focus-reset');
    DOM.focusPresetBtns = Array.from(document.querySelectorAll('.pomo-preset-btn'));
    DOM.alarmSoundSelect = document.getElementById('alarm-sound-select');
    DOM.btnTestAlarm = document.getElementById('btn-test-alarm');
    DOM.btnToggleNoise = document.getElementById('btn-toggle-noise');
    DOM.sliderNoiseVol = document.getElementById('slider-noise-vol');
    DOM.valNoiseVol = document.getElementById('val-noise-vol');

    // Tasks elements
    DOM.contractTaskList = document.getElementById('contract-task-list');
    DOM.completedTaskList = document.getElementById('completed-task-list');
    DOM.btnOpenPoisonModal = document.getElementById('btn-open-poison-modal');
    DOM.poisonModal = document.getElementById('poison-modal-overlay');
    DOM.btnClosePoison = document.getElementById('btn-close-poison');
    DOM.poisonOptionsGrid = document.getElementById('poison-options-grid');

    // Parking & Mirror
    DOM.parkingTimelineContainer = document.getElementById('parking-timeline-container');
    DOM.parkingCountBadge = document.getElementById('parking-count-badge');
    DOM.parkingViewInput = document.getElementById('parking-view-input');
    DOM.btnParkingViewAdd = document.getElementById('btn-parking-view-add');
    DOM.parkingViewFeedback = document.getElementById('parking-view-feedback');
    DOM.tileParkingCount = document.getElementById('tile-parking-count');
    DOM.tileParkingLatest = document.getElementById('tile-parking-latest');
    DOM.tileMirrorCount = document.getElementById('tile-mirror-count');
    DOM.tileMirrorStatus = document.getElementById('tile-mirror-status');
    DOM.lifeAltList = document.getElementById('life-alt-list');
    DOM.btnAddLifeAlt = document.getElementById('btn-add-life-alt');
    DOM.lifeModal = document.getElementById('life-modal-overlay');
    DOM.btnCloseLife = document.getElementById('btn-close-life');
    DOM.btnSaveLifeAlt = document.getElementById('btn-save-life-alt');
    DOM.newLifeLabel = document.getElementById('new-life-label');
    DOM.newLifeCategory = document.getElementById('new-life-category');
    DOM.newLifeDuration = document.getElementById('new-life-duration');

    // Backlog & Guard
    DOM.backlogTableContainer = document.getElementById('backlog-table-container');
    DOM.btnEvalAutofill = document.getElementById('btn-eval-autofill');
    DOM.guardTestPrompt = document.getElementById('guard-test-prompt');
    DOM.btnEvalPrompt = document.getElementById('btn-eval-prompt');
    DOM.guardVerdictBox = document.getElementById('guard-verdict-box');

    // Lockdown Modal
    DOM.btnLockdown = document.getElementById('btn-lockdown');
    DOM.lockdownModal = document.getElementById('lockdown-modal-overlay');
    DOM.btnCloseLockdown = document.getElementById('btn-close-lockdown');
    DOM.btnConfirmLockdown = document.getElementById('btn-confirm-lockdown');
    DOM.btnCancelLockdown = document.getElementById('btn-cancel-lockdown');

    // Settings elements
    DOM.btnSettings = document.getElementById('btn-settings');
    DOM.settingsOverlay = document.getElementById('settings-overlay');
    DOM.btnCloseSettings = document.getElementById('btn-close-settings');
    DOM.shellSliderBrightness = document.getElementById('shell-slider-brightness');
    DOM.shellSliderBlur = document.getElementById('shell-slider-blur');
    DOM.shellSliderOpacity = document.getElementById('shell-slider-opacity');
    DOM.shellValBrightness = document.getElementById('shell-val-brightness');
    DOM.shellValBlur = document.getElementById('shell-val-blur');
    DOM.shellValOpacity = document.getElementById('shell-val-opacity');
    DOM.shellThemeCardDark = document.getElementById('shell-theme-card-dark');
    DOM.shellThemeCardLight = document.getElementById('shell-theme-card-light');
    DOM.modalSliderBrightness = document.getElementById('slider-bg-brightness');
    DOM.modalSliderBlur = document.getElementById('slider-bg-blur');
    DOM.modalSliderOpacity = document.getElementById('slider-bg-opacity');
    DOM.modalValBrightness = document.getElementById('val-bg-brightness');
    DOM.modalValBlur = document.getElementById('val-bg-blur');
    DOM.modalValOpacity = document.getElementById('val-bg-opacity');
    DOM.modalThemeCardDark = document.getElementById('theme-card-dark');
    DOM.modalThemeCardLight = document.getElementById('theme-card-light');
    DOM.btnResetUnderlayShell = document.getElementById('btn-reset-underlay-shell');
    DOM.btnResetUnderlayModal = document.getElementById('btn-reset-underlay-modal');
    DOM.artPresetGrid = document.getElementById('art-preset-grid');
    DOM.quotesManagerList = document.getElementById('quotes-manager-list');
    DOM.streakRibbon = document.getElementById('stats-streak-ribbon');
    DOM.ledgerContainer = document.getElementById('ledger-events-container');
    DOM.topicsBreakdownContainer = document.getElementById('topics-breakdown-container');
    DOM.coOccurrenceContainer = document.getElementById('co-occurrence-chips-container');

    // Settings tabs & Local Gallery Studio elements
    DOM.settingsTabs = document.querySelectorAll('.settings-tabs-nav .tab-btn');
    DOM.tabPanes = document.querySelectorAll('.settings-tab-content .tab-pane');
    DOM.artUploadDropzone = document.getElementById('art-upload-dropzone');
    DOM.localArtFileInput = document.getElementById('local-art-file-input');
    DOM.btnBrowseImages = document.getElementById('btn-browse-images');
    DOM.uploadProgressWrap = document.getElementById('upload-progress-wrap');
    DOM.uploadProgressFill = document.getElementById('upload-progress-fill');
    DOM.uploadProgressText = document.getElementById('upload-progress-text');
    DOM.localImagesCountPill = document.getElementById('local-images-count-pill');
    DOM.checkCycleUserUploads = document.getElementById('check-cycle-user-uploads');
    DOM.btnRefreshGallery = document.getElementById('btn-refresh-gallery');
    DOM.localArtGrid = document.getElementById('local-art-grid');
    DOM.galleryServerStatus = document.getElementById('gallery-server-status');
    DOM.galleryStatusText = document.getElementById('gallery-status-text');
    DOM.customArtUrl = document.getElementById('custom-art-url');
    DOM.btnAddArt = document.getElementById('btn-add-art');

    // Artwork Sets & Collections elements
    DOM.artSetsGrid = document.getElementById('art-sets-grid');
    DOM.artSetsCountPill = document.getElementById('art-sets-count-pill');
    DOM.galleryActiveSetLabel = document.getElementById('gallery-active-set-label');
    DOM.setInspectorOverlay = document.getElementById('set-inspector-overlay');
    DOM.setInspectorTitle = document.getElementById('set-inspector-title');
    DOM.setInspectorCount = document.getElementById('set-inspector-count');
    DOM.setInspectorGrid = document.getElementById('set-inspector-grid');
    DOM.btnUseInspectedSet = document.getElementById('btn-use-inspected-set');
    DOM.btnCloseInspector = document.getElementById('btn-close-inspector');
    DOM.uploadSetModalOverlay = document.getElementById('upload-set-modal-overlay');
    DOM.uploadTargetSetSelect = document.getElementById('upload-target-set-select');
    DOM.groupNewSetName = document.getElementById('group-new-set-name');
    DOM.inputNewSetName = document.getElementById('input-new-set-name');
    DOM.btnCancelUploadSet = document.getElementById('btn-cancel-upload-set');
    DOM.btnConfirmUploadSet = document.getElementById('btn-confirm-upload-set');
    DOM.uploadSetFilesCount = document.getElementById('upload-set-files-count');
    DOM.btnCloseUploadSetModal = document.getElementById('btn-close-upload-set-modal');
  }

  // --- Dual-Mode Router ---
  function setMode(newMode) {
    state.mode = newMode;
    if (newMode === 'dashboard') {
      DOM.body.classList.remove('mode-picture');
      DOM.body.classList.add('mode-dashboard');
      DOM.appShell.style.display = 'flex';
      if (DOM.modeBadgeText) DOM.modeBadgeText.textContent = 'Dashboard Shell';
      if (DOM.btnToggleText) DOM.btnToggleText.textContent = 'Still Mode';
      if (window.DhritiBubbles && typeof window.DhritiBubbles.clear === 'function') {
        window.DhritiBubbles.clear();
      }
      showView(state.currentView || 'desk');
      drawDonutChart();
      renderTopicBars();
    } else {
      DOM.body.classList.remove('mode-dashboard');
      DOM.body.classList.add('mode-picture');
      DOM.appShell.style.display = 'none';
      if (DOM.modeBadgeText) DOM.modeBadgeText.textContent = 'Still Mode';
      if (DOM.btnToggleText) DOM.btnToggleText.textContent = 'Enter Dashboard Shell';
      if (window.DhritiBubbles && typeof window.DhritiBubbles.updateLoopState === 'function') {
        window.DhritiBubbles.updateLoopState();
      }
      drawDonutChart();
    }
  }

  function showView(viewId) {
    state.currentView = viewId;
    DOM.navItems.forEach(btn => {
      btn.classList.toggle('active', btn.dataset.view === viewId);
    });
    DOM.shellViews.forEach(view => {
      view.classList.toggle('active', view.id === `view-${viewId}`);
    });

    if (viewId === 'desk') {
      drawDonutChart();
      renderTopicBars();
    } else if (viewId === 'tasks') {
      renderContractTasks();
    } else if (viewId === 'completed') {
      renderCompletedTasks();
    } else if (viewId === 'topics') {
      renderTopicsView();
    } else if (viewId === 'parking') {
      renderParkingTimeline();
    } else if (viewId === 'mirror') {
      renderLifeAlts();
    } else if (viewId === 'backlog') {
      renderBacklogTable();
    } else if (viewId === 'stats') {
      renderStreakRibbon();
    } else if (viewId === 'ledger') {
      renderLedgerTable();
    }
  }

  // --- Solitaire / Minesweeper Wave Sweep Flip ---
  function flipToDashboard() {
    if (state.mode === 'dashboard') return;
    if (window.DhritiAudio) window.DhritiAudio.playFlipClick(0.8);

    // Wave cascade flip on tactile tiles
    DOM.tiles.forEach((tile, idx) => {
      const delay = idx * 60;
      setTimeout(() => {
        tile.classList.add('is-flipped');
        if (window.DhritiAudio && idx % 2 === 0) window.DhritiAudio.playChime(idx, 0.3);
      }, delay);
    });

    setTimeout(() => {
      setMode('dashboard');
    }, DOM.tiles.length * 60 + 350);
  }

  function returnToArt() {
    setMode('picture');
    DOM.tiles.forEach(tile => tile.classList.remove('is-flipped'));
    if (window.DhritiAudio) window.DhritiAudio.playChime(0, 0.4);
  }

  // --- Theme Controller ---
  function setTheme(newTheme) {
    state.theme = newTheme;
    if (newTheme === 'light') {
      DOM.body.classList.remove('theme-dark');
      DOM.body.classList.add('theme-light');
      if (DOM.themeIconDark) DOM.themeIconDark.style.display = 'none';
      if (DOM.themeIconLight) DOM.themeIconLight.style.display = 'block';
    } else {
      DOM.body.classList.remove('theme-light');
      DOM.body.classList.add('theme-dark');
      if (DOM.themeIconDark) DOM.themeIconDark.style.display = 'block';
      if (DOM.themeIconLight) DOM.themeIconLight.style.display = 'none';
    }

    // Keep theme selector cards in sync across Settings view and modal
    if (DOM.shellThemeCardDark) DOM.shellThemeCardDark.classList.toggle('active', newTheme === 'dark');
    if (DOM.shellThemeCardLight) DOM.shellThemeCardLight.classList.toggle('active', newTheme === 'light');
    const modalDark = document.getElementById('theme-card-dark');
    const modalLight = document.getElementById('theme-card-light');
    if (modalDark) modalDark.classList.toggle('active', newTheme === 'dark');
    if (modalLight) modalLight.classList.toggle('active', newTheme === 'light');

    updateUnderlayStyles();
    drawDonutChart();
  }

  function updateUnderlayStyles() {
    const root = document.documentElement;
    root.style.setProperty('--dash-bg-brightness', state.underlay.brightness / 100);
    root.style.setProperty('--dash-bg-blur', `${state.underlay.blur}px`);
    root.style.setProperty('--dash-bg-opacity', state.underlay.opacity / 100);

    // Persist to local storage
    try {
      localStorage.setItem('dhriti_bg_brightness', state.underlay.brightness);
      localStorage.setItem('dhriti_bg_blur', state.underlay.blur);
      localStorage.setItem('dhriti_bg_opacity', state.underlay.opacity);
    } catch (e) {}

    // Sync input sliders and labels across Settings view and modal
    if (DOM.shellSliderBrightness) DOM.shellSliderBrightness.value = state.underlay.brightness;
    if (DOM.shellSliderBlur) DOM.shellSliderBlur.value = state.underlay.blur;
    if (DOM.shellSliderOpacity) DOM.shellSliderOpacity.value = state.underlay.opacity;
    if (DOM.shellValBrightness) DOM.shellValBrightness.textContent = `${state.underlay.brightness}%`;
    if (DOM.shellValBlur) DOM.shellValBlur.textContent = `${state.underlay.blur} px`;
    if (DOM.shellValOpacity) DOM.shellValOpacity.textContent = `${state.underlay.opacity}%`;

    if (DOM.modalSliderBrightness) DOM.modalSliderBrightness.value = state.underlay.brightness;
    if (DOM.modalSliderBlur) DOM.modalSliderBlur.value = state.underlay.blur;
    if (DOM.modalSliderOpacity) DOM.modalSliderOpacity.value = state.underlay.opacity;
    if (DOM.modalValBrightness) DOM.modalValBrightness.textContent = `${state.underlay.brightness}%`;
    if (DOM.modalValBlur) DOM.modalValBlur.textContent = `${state.underlay.blur} px`;
    if (DOM.modalValOpacity) DOM.modalValOpacity.textContent = `${state.underlay.opacity}%`;
  }

  function resetUnderlayDefaults() {
    state.underlay = {
      brightness: 100,
      blur: 0,
      opacity: 100
    };
    setTheme('dark');
    updateUnderlayStyles();
    if (window.DhritiAudio) window.DhritiAudio.playChime(5, 0.35);
  }

  // --- Donut Chart Renderer (Canvas-based for Desk & Mode 1 Tile 2) ---
  function drawDonutChart() {
    const canvases = [DOM.donutCanvas, document.getElementById('tile-donut-stage-canvas')].filter(Boolean);
    canvases.forEach(canvas => {
      const ctx = canvas.getContext('2d');
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const centerX = w / 2;
      const centerY = h / 2;
      const radius = Math.min(centerX, centerY) - 18;
      const thickness = 14;

      const stagePct = 0.88;
      const startAngle = -Math.PI / 2;
      const stageAngle = startAngle + (Math.PI * 2 * stagePct);

      // Track
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
      ctx.strokeStyle = state.theme === 'dark' ? '#2a304e' : '#e2e8f0';
      ctx.lineWidth = thickness;
      ctx.stroke();

      // Stage Arc
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius, startAngle, stageAngle);
      ctx.strokeStyle = state.theme === 'dark' ? '#8b78f6' : '#00b894';
      ctx.lineWidth = thickness;
      ctx.lineCap = 'round';
      ctx.stroke();

      // Center text with Poiret One font
      ctx.fillStyle = state.theme === 'dark' ? '#ffffff' : '#0f172a';
      ctx.font = '700 22px "Poiret One", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('88%', centerX, centerY - 2);

      ctx.fillStyle = state.theme === 'dark' ? '#a0a7c4' : '#64748b';
      ctx.font = 'italic 700 10px "Poiret One", sans-serif';
      ctx.fillText('STAGE', centerX, centerY + 14);
    });
  }

  // --- Topic-Time Stacked Bar Distribution (D-091 / L-11) ---
  function renderTopicBars() {
    if (!DOM.deskTopicBars) return;
    DOM.deskTopicBars.innerHTML = '';

    const maxMinutes = Math.max(...state.topicTime.map(t => t.duration_min), 1);

    state.topicTime.forEach(item => {
      const row = document.createElement('div');
      row.className = 'topic-bar-row';

      const hours = (item.duration_min / 60).toFixed(1);
      const widthPct = Math.min(100, (item.duration_min / maxMinutes) * 100);

      row.innerHTML = `
        <div class="topic-bar-meta">
          <span><strong>${item.domain}</strong> — ${item.category}</span>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span>${hours}h (${item.duration_min}m)</span>
            <button type="button" class="btn-remove-item" data-remove-topic="${item.id}" title="Remove topic">✕</button>
          </div>
        </div>
        <div class="topic-bar-track">
          <div class="topic-bar-seg ${item.is_stage ? 'stage' : 'audience'}" style="width: ${widthPct}%;"></div>
        </div>
      `;
      DOM.deskTopicBars.appendChild(row);
    });

    // Wire topic removal
    DOM.deskTopicBars.querySelectorAll('[data-remove-topic]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const tid = btn.getAttribute('data-remove-topic');
        state.topicTime = state.topicTime.filter(t => t.id !== tid);
        renderTopicBars();
        drawDonutChart();
      });
    });
  }

  // --- Active Tasks & Balancer (D-093) ---
  function renderContractTasks() {
    if (!DOM.contractTaskList) return;
    DOM.contractTaskList.innerHTML = '';

    state.activeTasks.forEach((task, idx) => {
      const row = document.createElement('div');
      row.className = 'task-item-row';
      row.innerHTML = `
        <div class="task-item-left">
          <input type="checkbox" class="task-checkbox" data-index="${idx}" ${task.done ? 'checked' : ''}>
          <span class="task-name" style="${task.done ? 'text-decoration: line-through; opacity: 0.6;' : ''}">${task.title}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="task-units-badge">${task.units}u</span>
          <span class="card-badge ${task.done ? 'success' : 'info'}">${task.proof}</span>
          <button type="button" class="btn-remove-item" data-remove-task="${task.id}" title="Remove target">✕</button>
        </div>
      `;
      DOM.contractTaskList.appendChild(row);
    });

    // Wire checkboxes
    DOM.contractTaskList.querySelectorAll('.task-checkbox').forEach(cb => {
      cb.addEventListener('change', e => {
        const i = parseInt(e.target.dataset.index, 10);
        state.activeTasks[i].done = e.target.checked;
        if (e.target.checked && window.DhritiAudio) {
          window.DhritiAudio.playBell();
        }
        renderContractTasks();
      });
    });

    // Wire task removal
    DOM.contractTaskList.querySelectorAll('[data-remove-task]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const tid = btn.getAttribute('data-remove-task');
        state.activeTasks = state.activeTasks.filter(t => t.id !== tid);
        renderContractTasks();
      });
    });
  }

  function renderCompletedTasks() {
    if (!DOM.completedTaskList) return;
    DOM.completedTaskList.innerHTML = '';
    state.completedTasks.forEach(task => {
      const row = document.createElement('div');
      row.className = 'task-item-row';
      row.innerHTML = `
        <div>
          <span class="task-name">${task.title}</span>
          <div style="font-size: 11px; color: var(--text-dim); margin-top: 2px;">Verified at ${task.timestamp}</div>
        </div>
        <span class="card-badge success">${task.proof}</span>
      `;
      DOM.completedTaskList.appendChild(row);
    });
  }

  // --- Pick Your Poison Equivalence Solver (D-093) ---
  function openPickYourPoison() {
    if (!DOM.poisonOptionsGrid) return;
    DOM.poisonOptionsGrid.innerHTML = '';

    // Generate 3 balanced equivalence options (each sum to ~2.0 - 2.5u)
    const options = [
      {
        label: 'Option A: Analytical & Testing Focus',
        units: 2.0,
        items: ['Verify FTS5 virtual table synchronization (2u)']
      },
      {
        label: 'Option B: Balanced Core & Review',
        units: 2.0,
        items: ['Write synthesized chime procedural tests (1u)', 'Review topic tokenizer stopwords (0.5u)', 'Format topic-time stacked bar (0.5u)']
      },
      {
        label: 'Option C: Architecture Deep-Dive',
        units: 2.5,
        items: ['Implement Vidura topic tree tests (2u)', 'Review topic tokenizer stopwords (0.5u)']
      }
    ];

    options.forEach(opt => {
      const card = document.createElement('div');
      card.className = 'poison-card';
      card.innerHTML = `
        <div class="poison-card-head">
          <span>${opt.label}</span>
          <span>${opt.units} Units</span>
        </div>
        <ul style="font-size: 13px; color: var(--text-muted); margin-left: 18px; margin-top: 6px;">
          ${opt.items.map(it => `<li>${it}</li>`).join('')}
        </ul>
      `;
      card.addEventListener('click', () => {
        // Adopt option into active contract
        opt.items.forEach(it => {
          state.activeTasks.push({
            id: `task-${Date.now()}-${Math.random().toString(36).substring(7)}`,
            title: it,
            units: 1.0,
            proof: 'evidence_check',
            done: false
          });
        });
        DOM.poisonModal.classList.remove('active');
        renderContractTasks();
        if (window.DhritiAudio) window.DhritiAudio.playBell();
      });
      DOM.poisonOptionsGrid.appendChild(card);
    });

    DOM.poisonModal.classList.add('active');
  }

  // --- Pomodoro Focus Engine ---
  function updateTimerDisplay() {
    const mins = Math.floor(state.pomodoro.remaining / 60);
    const secs = state.pomodoro.remaining % 60;
    const str = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

    if (DOM.focusBigTimer) DOM.focusBigTimer.textContent = str;
    if (DOM.miniTimerDisplay) DOM.miniTimerDisplay.textContent = str;
    const tilePomo = document.getElementById('tile-pomo-time');
    if (tilePomo) tilePomo.textContent = str;

    // Persistent Header Pomodoro Timer Pill update
    if (DOM.headerPomoTime) DOM.headerPomoTime.textContent = str;
    if (DOM.headerPomoPhase) DOM.headerPomoPhase.textContent = state.pomodoro.mode === 'break' ? 'REST' : 'FOCUS';
    if (DOM.headerPomoPill) {
      if (state.pomodoro.isRunning) {
        DOM.headerPomoPill.classList.add('running');
        if (DOM.headerPomoPlayIcon) DOM.headerPomoPlayIcon.style.display = 'none';
        if (DOM.headerPomoPauseIcon) DOM.headerPomoPauseIcon.style.display = 'block';
      } else {
        DOM.headerPomoPill.classList.remove('running');
        if (DOM.headerPomoPlayIcon) DOM.headerPomoPlayIcon.style.display = 'block';
        if (DOM.headerPomoPauseIcon) DOM.headerPomoPauseIcon.style.display = 'none';
      }
    }
  }

  function togglePomodoro() {
    if (state.pomodoro.isRunning) {
      clearInterval(state.pomodoro.timerId);
      state.pomodoro.isRunning = false;
      DOM.btnFocusStart.textContent = state.pomodoro.phase === 'break' ? 'Resume Break' : 'Resume Focus';
      if (DOM.miniTimerPill) DOM.miniTimerPill.style.display = 'none';
      updateTimerDisplay(); // Immediately flip || icon back to ▶
    } else {
      const preset = state.pomodoro.presets[state.pomodoro.mode];
      const maxTime = state.pomodoro.phase === 'break' ? preset.break : preset.focus;
      const isStartingFresh = (state.pomodoro.remaining === maxTime);

      state.pomodoro.isRunning = true;
      DOM.btnFocusStart.textContent = state.pomodoro.phase === 'break' ? 'Pause Break' : 'Pause Focus';
      if (DOM.miniTimerPill) DOM.miniTimerPill.style.display = 'none';
      updateTimerDisplay(); // Immediately flip ▶ icon to ||

      // Ring Tibetan Singing Bowl tone when starting from scratch
      if (isStartingFresh && window.DhritiAudio) {
        window.DhritiAudio.playProceduralAlarm('singing_bowl');
      }

      state.pomodoro.timerId = setInterval(() => {
        if (state.pomodoro.remaining > 0) {
          state.pomodoro.remaining--;
          updateTimerDisplay();
        } else {
          // Timer finished! Ring Tibetan sound to signal end of period
          clearInterval(state.pomodoro.timerId);
          state.pomodoro.isRunning = false;
          if (DOM.miniTimerPill) DOM.miniTimerPill.style.display = 'none';

          if (window.DhritiAudio) {
            window.DhritiAudio.playProceduralAlarm('singing_bowl');
          }

          if (state.pomodoro.phase === 'focus') {
            // Focus period ended -> transition to Break
            state.pomodoro.phase = 'break';
            state.pomodoro.remaining = preset.break;
            DOM.btnFocusStart.textContent = 'Start Break';
          } else {
            // Break period ended -> transition back to Focus
            state.pomodoro.phase = 'focus';
            state.pomodoro.remaining = preset.focus;
            DOM.btnFocusStart.textContent = 'Start Focus';
          }
          updateTimerDisplay();
        }
      }, 1000);
    }
  }

  function resetPomodoro() {
    clearInterval(state.pomodoro.timerId);
    state.pomodoro.isRunning = false;
    DOM.btnFocusStart.textContent = 'Start Focus';
    if (DOM.miniTimerPill) DOM.miniTimerPill.style.display = 'none';
    state.pomodoro.phase = 'focus';
    const preset = state.pomodoro.presets[state.pomodoro.mode];
    state.pomodoro.remaining = preset.focus;
    updateTimerDisplay();

    // Ring Tibetan sound whenever timer resets or restarts from scratch
    if (window.DhritiAudio) {
      window.DhritiAudio.playProceduralAlarm('singing_bowl');
    }
  }

  // --- Life Alternatives Data Synchronization ---
  function getLifeAlternatives() {
    return state.lifeAlts || [];
  }

  // --- Parking Timeline View ---
  function renderParkingTimeline() {
    if (DOM.parkingCountBadge) {
      DOM.parkingCountBadge.textContent = `${state.parkingItems.length} Item${state.parkingItems.length === 1 ? '' : 's'}`;
    }
    if (DOM.tileParkingCount) {
      DOM.tileParkingCount.textContent = `${state.parkingItems.length} waiting`;
    }
    if (DOM.tileParkingLatest) {
      DOM.tileParkingLatest.textContent = state.parkingItems.length > 0
        ? state.parkingItems[0].text
        : 'Parking lot clear. Zero items waiting.';
    }

    if (!DOM.parkingTimelineContainer) return;
    DOM.parkingTimelineContainer.innerHTML = '';

    if (state.parkingItems.length === 0) {
      DOM.parkingTimelineContainer.innerHTML = `
        <div style="padding: 24px; text-align: center; color: var(--text-dim); font-style: italic;">
          No parked thoughts waiting. Use the field above to park a mid-session curiosity for cold review.
        </div>
      `;
      return;
    }

    state.parkingItems.forEach((item, idx) => {
      const card = document.createElement('div');
      card.className = 'task-item-row';
      card.innerHTML = `
        <div>
          <span class="task-name">${item.text}</span>
          <div style="font-size: 11px; color: var(--text-dim); margin-top: 3px;">Age: ${item.age_days} day(s) • Type: ${item.type}</div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn-primary" style="padding: 6px 12px; font-size: 11px;" data-park-action="approve" data-index="${idx}">Approve to Contract</button>
          <button class="btn-sec" style="padding: 6px 12px; font-size: 11px;" data-park-action="drop" data-index="${idx}">Drop</button>
        </div>
      `;
      DOM.parkingTimelineContainer.appendChild(card);
    });

    DOM.parkingTimelineContainer.querySelectorAll('button[data-park-action]').forEach(btn => {
      btn.addEventListener('click', e => {
        const action = e.target.dataset.parkAction;
        const i = parseInt(e.target.dataset.index, 10);
        if (action === 'approve') {
          state.activeTasks.push({
            id: `task-${Date.now()}`,
            title: state.parkingItems[i].text,
            units: 1.0,
            proof: 'cold_approved',
            done: false
          });
        }
        state.parkingItems.splice(i, 1);
        renderParkingTimeline();
      });
    });
  }

  // --- Life Alternatives View (Surfaced exclusively via Thought Bubbles D-092) ---
  function renderLifeAlts() {
    if (DOM.tileMirrorCount) {
      DOM.tileMirrorCount.textContent = `${state.lifeAlts.length} offline item${state.lifeAlts.length === 1 ? '' : 's'}`;
    }
    if (!DOM.lifeAltList) return;
    DOM.lifeAltList.innerHTML = '';
    const shapes = ['shape-cloud', 'shape-oval', 'shape-rect'];
    state.lifeAlts.forEach((alt, idx) => {
      const chip = document.createElement('div');
      const shape = shapes[idx % shapes.length];
      chip.className = `bubble-alt-chip ${shape}`;
      chip.innerHTML = `
        <button type="button" class="chip-remove-btn" data-remove-life="${alt.id}" title="Remove alternative">✕</button>
        <div class="chip-quote">“${alt.label}”</div>
        <div class="chip-meta">${alt.duration ? alt.duration + 'm' : 'Offline'} • ${alt.category || 'Rest'}</div>
      `;
      chip.title = "Click to release this thought bubble across the screen";
      chip.addEventListener('click', (e) => {
        if (e.target.closest('.chip-remove-btn')) return;
        if (window.DhritiBubbles && typeof window.DhritiBubbles.spawnNow === 'function') {
          window.DhritiBubbles.spawnNow(alt.label);
        }
      });
      DOM.lifeAltList.appendChild(chip);
    });

    // Wire life alternative removal
    DOM.lifeAltList.querySelectorAll('[data-remove-life]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const lid = btn.getAttribute('data-remove-life');
        state.lifeAlts = state.lifeAlts.filter(a => a.id !== lid);
        try { localStorage.setItem('dhriti_life_alts', JSON.stringify(state.lifeAlts)); } catch (err) {}
        if (window.DhritiBubbles && typeof window.DhritiBubbles.refreshFeed === 'function') {
          window.DhritiBubbles.refreshFeed();
        }
        renderLifeAlts();
      });
    });
  }

  // --- Dynamic Backlog View ---
  function renderBacklogTable() {
    if (!DOM.backlogTableContainer) return;
    DOM.backlogTableContainer.innerHTML = '';
    state.backlog.forEach((item, idx) => {
      const row = document.createElement('div');
      row.className = 'task-item-row';
      row.innerHTML = `
        <span class="task-name">${item.title}</span>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="task-units-badge">${item.units}u (${item.tier})</span>
          <button class="btn-primary" style="padding: 6px 12px; font-size: 11px;" data-backlog-add="${idx}">Add to Day</button>
        </div>
      `;
      DOM.backlogTableContainer.appendChild(row);
    });

    DOM.backlogTableContainer.querySelectorAll('button[data-backlog-add]').forEach(btn => {
      btn.addEventListener('click', e => {
        const i = parseInt(e.target.dataset.backlogAdd, 10);
        const item = state.backlog[i];
        state.activeTasks.push({
          id: item.id,
          title: item.title,
          units: item.units,
          proof: 'evidence_check',
          done: false
        });
        state.backlog.splice(i, 1);
        renderBacklogTable();
      });
    });
  }

  // --- Prompt Inspection / Guard Governor ---
  function evaluatePromptAlignment() {
    const promptText = DOM.guardTestPrompt.value.trim();
    if (!promptText) return;

    const topicWords = ['dhriti', 'tactile', 'dashboard', 'architecture', 'token', 'sqlite', 'chime', 'bridge'];
    const promptTokens = promptText.toLowerCase().split(/\W+/);
    const overlap = promptTokens.filter(t => topicWords.includes(t));

    DOM.guardVerdictBox.style.display = 'block';
    if (overlap.length >= 1) {
      DOM.guardVerdictBox.innerHTML = `
        <div class="capsule-box" style="border-color: var(--accent-emerald);">
          <div class="capsule-key" style="color: var(--accent-emerald);">Verdict: On-Topic (Aligned)</div>
          <div class="capsule-value">Matching topic stems: [${overlap.join(', ')}]. Prompt accepted silently.</div>
        </div>
      `;
    } else {
      DOM.guardVerdictBox.innerHTML = `
        <div class="capsule-box" style="border-color: var(--accent-amber);">
          <div class="capsule-key" style="color: var(--accent-amber);">Verdict: Divergent (Topic Drift)</div>
          <div class="capsule-value">No shared stems with active contract topic. In strict session, turn is held for cold review.</div>
        </div>
      `;
    }
  }

  // --- Honest Stats View (L-2: 7-Day Daemon Active Time Distribution) ---
  function renderStreakRibbon() {
    if (!DOM.streakRibbon) return;
    DOM.streakRibbon.innerHTML = '';

    // Honest 7-Day timeline (never claiming past days met before project began)
    const weekData = [
      { day: 'Mon', hours: 0, label: '0h', active: false },
      { day: 'Tue', hours: 0, label: '0h', active: false },
      { day: 'Wed', hours: 0, label: '0h', active: false },
      { day: 'Thu', hours: 0, label: '0h', active: false },
      { day: 'Fri', hours: 0, label: '0h', active: false },
      { day: 'Sat', hours: 0, label: '0h', active: false },
      { day: 'Today', hours: 2.4, label: '2.4h', active: true, isToday: true }
    ];

    const maxHours = 4.0;

    weekData.forEach(item => {
      const col = document.createElement('div');
      col.className = `daemon-bar-col ${item.active ? 'active' : 'inactive'} ${item.isToday ? 'today' : ''}`;
      const fillPct = item.hours > 0 ? Math.min(100, Math.round((item.hours / maxHours) * 100)) : 4;
      col.innerHTML = `
        <span class="daemon-bar-time">${item.label}</span>
        <div class="daemon-bar-track">
          <div class="daemon-bar-fill" style="height: ${fillPct}%;"></div>
        </div>
        <span class="daemon-bar-label">${item.day}</span>
      `;
      DOM.streakRibbon.appendChild(col);
    });
  }

  // --- Audit Ledger View ---
  function renderLedgerTable() {
    if (!DOM.ledgerContainer) return;
    DOM.ledgerContainer.innerHTML = '';
    const events = [
      { ts: '13:05:12', action: 'TOPIC_DAY_HISTOGRAM_COMPUTED', hash: 'e3b0c442...98fc' },
      { ts: '12:48:30', action: 'CONTRACT_PROOF_SUBMITTED', hash: 'a1b2c3d4...ef56' },
      { ts: '12:15:00', action: 'POMODORO_INTERVAL_STARTED', hash: 'f6e5d4c3...b2a1' },
      { ts: '11:30:22', action: 'LIFE_ALTERNATIVE_DECLARED', hash: '98765432...10fe' },
      { ts: '08:00:00', action: 'DAY_WINDOW_OPENED', hash: '12345678...90ab' }
    ];
    events.forEach(ev => {
      const row = document.createElement('div');
      row.className = 'task-item-row';
      row.innerHTML = `
        <div>
          <span class="task-name">${ev.action}</span>
          <div style="font-size: 11px; color: var(--text-dim); margin-top: 2px;">Timestamp: ${ev.ts}</div>
        </div>
        <span class="card-badge info">${ev.hash}</span>
      `;
      DOM.ledgerContainer.appendChild(row);
    });
  }

  // --- Topics & Co-occurrence View ---
  function renderTopicsView() {
    if (DOM.topicsBreakdownContainer) {
      DOM.topicsBreakdownContainer.innerHTML = `
        <div class="metric-row"><span class="metric-label">Compiler & Rust Architecture</span><span class="metric-val">120m</span></div>
        <div class="metric-row"><span class="metric-label">Procedural Web Audio API</span><span class="metric-val">65m</span></div>
        <div class="metric-row"><span class="metric-label">Verlet Physics & Doorway Beads</span><span class="metric-val">45m</span></div>
        <div class="metric-row"><span class="metric-label">FTS5 SQLite Indexing</span><span class="metric-val">30m</span></div>
      `;
    }
    if (DOM.coOccurrenceContainer) {
      DOM.coOccurrenceContainer.innerHTML = `
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <span class="author-chip">compiler + rust</span>
          <span class="author-chip">audio + oscillator</span>
          <span class="author-chip">chimes + verlet</span>
          <span class="author-chip">fts5 + sqlite</span>
          <span class="author-chip">springboard + search</span>
        </div>
      `;
    }
  }

  // --- Local Artwork & Image Studio Engine ---

  function wireSettingsTabs() {
    if (!DOM.settingsTabs) return;
    DOM.settingsTabs.forEach(tabBtn => {
      tabBtn.addEventListener('click', () => {
        DOM.settingsTabs.forEach(b => b.classList.remove('active'));
        DOM.tabPanes.forEach(p => p.classList.remove('active'));
        tabBtn.classList.add('active');
        const targetId = tabBtn.dataset.tab;
        const targetPane = document.getElementById(targetId);
        if (targetPane) targetPane.classList.add('active');
      });
    });
  }

  // --- Curated Artwork Sets & Collections Architecture ---
  function getInitialArtSets() {
    let saved = null;
    try {
      saved = JSON.parse(localStorage.getItem('dhriti_art_sets'));
    } catch (e) {}

    if (saved && Array.isArray(saved) && saved.length > 0) {
      return saved;
    }

    const defaultSet = {
      id: 'set-curated-museum',
      name: 'Curated Museum Masterpieces',
      isDefault: true,
      images: [...DEFAULT_ARTWORKS]
    };

    let localSaved = [];
    try {
      localSaved = JSON.parse(localStorage.getItem('dhriti_local_gallery') || '[]');
    } catch (e) {}

    const sets = [defaultSet];
    if (localSaved.length > 0) {
      sets.push({
        id: 'set-local-uploads',
        name: 'My Local Uploads',
        isDefault: false,
        images: localSaved
      });
    }

    try {
      localStorage.setItem('dhriti_art_sets', JSON.stringify(sets));
    } catch (e) {}
    return sets;
  }

  function saveArtSets() {
    try {
      localStorage.setItem('dhriti_art_sets', JSON.stringify(state.artSets));
      localStorage.setItem('dhriti_active_set_id', state.activeSetId);
      localStorage.setItem('dhriti_active_art', state.activeArtId);
      const allLocal = [];
      state.artSets.forEach(s => {
        if (!s.isDefault) allLocal.push(...s.images);
      });
      localStorage.setItem('dhriti_local_gallery', JSON.stringify(allLocal));
    } catch (e) {}
  }

  async function loadGallery() {
    state.artSets = getInitialArtSets();

    let serverImages = [];
    let isServer = false;
    try {
      const resp = await fetch('/api/gallery/images');
      if (resp.ok) {
        const data = await resp.json();
        serverImages = data.images || [];
        isServer = true;
      }
    } catch (e) {}

    if (isServer) {
      if (DOM.galleryServerStatus) {
        DOM.galleryServerStatus.classList.remove('offline');
        if (DOM.galleryStatusText) DOM.galleryStatusText.textContent = 'Local Server Permanent Storage';
      }
      state.localArtworks = serverImages;
      if (serverImages.length > 0) {
        let localSet = state.artSets.find(s => s.id === 'set-local-uploads');
        if (!localSet) {
          localSet = { id: 'set-local-uploads', name: 'My Local Uploads', isDefault: false, images: [] };
          state.artSets.push(localSet);
        }
        serverImages.forEach(img => {
          if (!localSet.images.some(i => i.filename === img.filename)) {
            localSet.images.push(img);
          }
        });
        saveArtSets();
      }
    } else {
      if (DOM.galleryServerStatus) {
        DOM.galleryServerStatus.classList.add('offline');
        if (DOM.galleryStatusText) DOM.galleryStatusText.textContent = 'Browser Storage (Offline/Static)';
      }
    }

    renderArtSets();
    applyActiveArtwork();
  }

  function renderArtSets() {
    if (!DOM.artSetsGrid) return;
    DOM.artSetsGrid.innerHTML = '';

    const count = state.artSets.length;
    if (DOM.artSetsCountPill) {
      DOM.artSetsCountPill.textContent = `${count} collection${count === 1 ? '' : 's'}`;
    }

    const activeSet = state.artSets.find(s => s.id === state.activeSetId) || state.artSets[0];
    if (DOM.galleryActiveSetLabel && activeSet) {
      DOM.galleryActiveSetLabel.textContent = `Active Set: ${activeSet.name}`;
    }

    state.artSets.forEach(set => {
      const card = document.createElement('div');
      const isActive = (state.activeSetId === set.id);
      card.className = `art-set-card ${isActive ? 'active' : ''} ${set.isDefault ? 'default' : ''}`;

      const img1 = set.images[0];
      const img2 = set.images[1];
      const img3 = set.images[2];

      card.innerHTML = `
        <div class="art-stack-container" title="Click to view artworks inside ${set.name}">
          ${img3 ? `<div class="art-stack-back layer-3" style="background-image: url('${img3.url}')"></div>` : ''}
          ${img2 ? `<div class="art-stack-back layer-2" style="background-image: url('${img2.url}')"></div>` : ''}
          ${img1 ? `<div class="art-stack-front" style="background-image: url('${img1.url}')"></div>` : '<div class="art-stack-front empty-stack">Empty Collection</div>'}
        </div>
        <div class="art-set-info">
          <div class="art-set-title-row">
            <span class="art-set-name">${set.name}</span>
            ${set.isDefault ? '<span class="set-badge default">Default Set</span>' : ''}
            ${isActive ? '<span class="set-badge active">Active Set</span>' : ''}
          </div>
          <div class="set-meta-row">
            <span class="set-count-pill">${set.images.length} artwork${set.images.length === 1 ? '' : 's'}</span>
          </div>
          <div class="art-set-actions">
            <button type="button" class="btn-sec btn-sm btn-open-set">Open Set</button>
            <button type="button" class="btn-primary btn-sm btn-use-set">${isActive ? 'In Use' : 'Use Set'}</button>
            ${!set.isDefault ? `<button type="button" class="btn-sec btn-sm btn-del-set" title="Delete set">Delete Set</button>` : ''}
          </div>
        </div>
      `;

      card.querySelector('.art-stack-container').addEventListener('click', () => openSetInspector(set.id));
      card.querySelector('.btn-open-set').addEventListener('click', () => openSetInspector(set.id));
      card.querySelector('.btn-use-set').addEventListener('click', () => activateSet(set.id));
      const delBtn = card.querySelector('.btn-del-set');
      if (delBtn) {
        delBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          deleteSet(set.id);
        });
      }

      DOM.artSetsGrid.appendChild(card);
    });
  }

  function openSetInspector(setId) {
    const set = state.artSets.find(s => s.id === setId);
    if (!set) return;
    state.inspectedSetId = setId;

    if (DOM.setInspectorTitle) DOM.setInspectorTitle.textContent = set.name;
    if (DOM.setInspectorCount) DOM.setInspectorCount.textContent = `${set.images.length} artwork${set.images.length === 1 ? '' : 's'}`;

    renderSetInspectorGrid(set);
    if (DOM.setInspectorOverlay) DOM.setInspectorOverlay.style.display = 'flex';
  }

  function renderSetInspectorGrid(set) {
    if (!DOM.setInspectorGrid) return;
    DOM.setInspectorGrid.innerHTML = '';

    if (set.images.length === 0) {
      DOM.setInspectorGrid.innerHTML = `
        <div class="gallery-empty-state" style="grid-column: 1 / -1;">
          <span>This collection has no images. Upload images into it above.</span>
        </div>
      `;
      return;
    }

    set.images.forEach(img => {
      const card = document.createElement('div');
      const isActive = (state.activeArtId === img.id);
      card.className = `set-img-card ${isActive ? 'active' : ''}`;

      card.innerHTML = `
        <img class="set-img-thumb" src="${img.url}" alt="${img.title}" loading="lazy">
        <div class="set-img-body">
          <div class="set-img-title" title="${img.title}">${img.title}</div>
          <div class="set-img-actions">
            <button type="button" class="btn-sec btn-sm btn-use-img">${isActive ? 'Active' : 'Use Art'}</button>
            <button type="button" class="btn-sec btn-sm btn-del-img" style="color: var(--accent-rose);" title="Delete picture">Delete</button>
          </div>
        </div>
      `;

      card.querySelector('.btn-use-img').addEventListener('click', () => {
        state.activeSetId = set.id;
        setActiveArtwork(img);
        renderSetInspectorGrid(set);
      });

      card.querySelector('.btn-del-img').addEventListener('click', (e) => {
        e.stopPropagation();
        deleteImageFromSet(set.id, img.id);
      });

      DOM.setInspectorGrid.appendChild(card);
    });
  }

  async function deleteImageFromSet(setId, imgId) {
    const set = state.artSets.find(s => s.id === setId);
    if (!set) return;
    const img = set.images.find(i => i.id === imgId);
    if (!img) return;

    if (!confirm(`Delete "${img.title}" from "${set.name}"?`)) return;

    if (img.filename) {
      try {
        await fetch('/api/gallery/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: img.filename })
        });
      } catch (e) {}
    }

    set.images = set.images.filter(i => i.id !== imgId);
    saveArtSets();

    if (state.activeArtId === imgId) {
      const fallbackImg = set.images[0] || (state.artSets[0] && state.artSets[0].images[0]) || DEFAULT_ARTWORKS[0];
      setActiveArtwork(fallbackImg);
    }

    if (DOM.setInspectorCount) DOM.setInspectorCount.textContent = `${set.images.length} artwork${set.images.length === 1 ? '' : 's'}`;
    renderSetInspectorGrid(set);
    renderArtSets();
    if (window.DhritiAudio) window.DhritiAudio.playChime(3, 0.25);
  }

  function deleteSet(setId) {
    const set = state.artSets.find(s => s.id === setId);
    if (!set || set.isDefault) return;

    if (!confirm(`Permanently delete the entire collection "${set.name}" (${set.images.length} artworks)?`)) return;

    set.images.forEach(img => {
      if (img.filename) {
        try {
          fetch('/api/gallery/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: img.filename })
          });
        } catch (e) {}
      }
    });

    state.artSets = state.artSets.filter(s => s.id !== setId);
    if (state.activeSetId === setId) {
      state.activeSetId = state.artSets[0].id;
      setActiveArtwork(state.artSets[0].images[0] || DEFAULT_ARTWORKS[0]);
    }

    saveArtSets();
    renderArtSets();
    if (window.DhritiAudio) window.DhritiAudio.playChime(3, 0.25);
  }

  function activateSet(setId) {
    const set = state.artSets.find(s => s.id === setId);
    if (!set) return;
    state.activeSetId = setId;
    localStorage.setItem('dhriti_active_set_id', setId);

    if (set.images.length > 0) {
      setActiveArtwork(set.images[0]);
    }
    renderArtSets();
    if (window.DhritiAudio) window.DhritiAudio.playChime(5, 0.35);
  }

  function setActiveArtwork(art) {
    if (!art || !art.url) return;
    state.activeArtId = art.id;
    localStorage.setItem('dhriti_active_art', art.id);

    document.documentElement.style.setProperty('--bg-image', `url('${art.url}')`);
    document.body.style.setProperty('--bg-image', `url('${art.url}')`);

    renderArtSets();
    if (state.inspectedSetId) {
      const inspected = state.artSets.find(s => s.id === state.inspectedSetId);
      if (inspected) renderSetInspectorGrid(inspected);
    }
    if (window.DhritiAudio) window.DhritiAudio.playChime(4, 0.28);
  }

  function applyActiveArtwork() {
    const activeSet = state.artSets.find(s => s.id === state.activeSetId) || state.artSets[0];
    let found = null;
    if (activeSet && activeSet.images) {
      found = activeSet.images.find(a => a.id === state.activeArtId);
      if (!found) found = activeSet.images[0];
    }
    if (!found) {
      found = DEFAULT_ARTWORKS[0];
    }
    if (found && found.url) {
      document.documentElement.style.setProperty('--bg-image', `url('${found.url}')`);
      document.body.style.setProperty('--bg-image', `url('${found.url}')`);
    }
  }

  function handleBatchImageUpload(files) {
    if (!files || files.length === 0) return;
    const validFiles = Array.from(files).filter(f => f.type.startsWith('image/'));
    if (validFiles.length === 0) {
      alert('Please select valid image files (JPEG, PNG, WEBP, GIF, SVG).');
      return;
    }

    state.pendingUploadFiles = validFiles;

    if (DOM.uploadSetFilesCount) {
      DOM.uploadSetFilesCount.textContent = `${validFiles.length} image${validFiles.length === 1 ? '' : 's'} selected to upload.`;
    }

    if (DOM.uploadTargetSetSelect) {
      DOM.uploadTargetSetSelect.innerHTML = '';
      state.artSets.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = `${s.name} (${s.images.length} images)`;
        if (s.id === state.activeSetId) opt.selected = true;
        DOM.uploadTargetSetSelect.appendChild(opt);
      });
      const newOpt = document.createElement('option');
      newOpt.value = '__new__';
      newOpt.textContent = '＋ Create a New Set...';
      DOM.uploadTargetSetSelect.appendChild(newOpt);
    }

    if (DOM.groupNewSetName) {
      DOM.groupNewSetName.style.display = (DOM.uploadTargetSetSelect && DOM.uploadTargetSetSelect.value === '__new__') ? 'block' : 'none';
    }
    if (DOM.inputNewSetName) DOM.inputNewSetName.value = '';

    if (DOM.uploadSetModalOverlay) DOM.uploadSetModalOverlay.style.display = 'flex';
  }

  async function confirmUploadIntoSet() {
    const files = state.pendingUploadFiles;
    if (!files || files.length === 0) return;

    let targetSetId = DOM.uploadTargetSetSelect ? DOM.uploadTargetSetSelect.value : '__new__';
    let targetSet = null;

    if (targetSetId === '__new__') {
      const newName = (DOM.inputNewSetName && DOM.inputNewSetName.value.trim()) || 'My Custom Collection';
      targetSet = {
        id: `set-${Date.now()}`,
        name: newName,
        isDefault: false,
        images: []
      };
      state.artSets.push(targetSet);
      targetSetId = targetSet.id;
    } else {
      targetSet = state.artSets.find(s => s.id === targetSetId);
    }

    if (!targetSet) return;

    if (DOM.uploadSetModalOverlay) DOM.uploadSetModalOverlay.style.display = 'none';
    if (DOM.uploadProgressWrap) DOM.uploadProgressWrap.style.display = 'block';

    let processed = 0;
    const total = files.length;

    for (const file of files) {
      if (DOM.uploadProgressText) {
        DOM.uploadProgressText.textContent = `Saving ${file.name} to "${targetSet.name}" (${processed + 1}/${total})...`;
      }
      if (DOM.uploadProgressFill) {
        DOM.uploadProgressFill.style.width = `${Math.round(((processed + 0.3) / total) * 100)}%`;
      }

      const dataUrl = await readFileAsDataURL(file);
      let uploadedImage = null;

      try {
        const resp = await fetch('/api/gallery/upload', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filename: file.name,
            title: file.name.replace(/\.[^/.]+$/, '').replace(/[_\-]/g, ' '),
            data: dataUrl
          })
        });
        if (resp.ok) {
          const resData = await resp.json();
          if (resData.ok && resData.image) {
            uploadedImage = resData.image;
          }
        }
      } catch (e) {}

      if (!uploadedImage) {
        uploadedImage = {
          id: `local-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
          title: file.name.replace(/\.[^/.]+$/, '').replace(/[_\-]/g, ' '),
          filename: file.name,
          url: dataUrl,
          size: file.size
        };
      }

      if (!targetSet.images.some(img => img.filename === uploadedImage.filename && img.id === uploadedImage.id)) {
        targetSet.images.unshift(uploadedImage);
      }

      processed++;
      if (DOM.uploadProgressFill) {
        DOM.uploadProgressFill.style.width = `${Math.round((processed / total) * 100)}%`;
      }
    }

    state.activeSetId = targetSet.id;
    if (targetSet.images.length > 0) {
      setActiveArtwork(targetSet.images[0]);
    }

    saveArtSets();

    setTimeout(() => {
      if (DOM.uploadProgressWrap) DOM.uploadProgressWrap.style.display = 'none';
      if (DOM.uploadProgressFill) DOM.uploadProgressFill.style.width = '0%';
    }, 1200);

    renderArtSets();
    if (window.DhritiAudio) window.DhritiAudio.playChime(6, 0.45);
  }

  function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function wireGalleryStudio() {
    if (DOM.btnBrowseImages && DOM.localArtFileInput) {
      DOM.btnBrowseImages.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        DOM.localArtFileInput.click();
      });
    }

    if (DOM.artUploadDropzone) {
      DOM.artUploadDropzone.addEventListener('click', (e) => {
        if (e.target !== DOM.btnBrowseImages && DOM.localArtFileInput) {
          DOM.localArtFileInput.click();
        }
      });

      const dropzone = DOM.artUploadDropzone;
      ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, e => {
          e.preventDefault();
          e.stopPropagation();
          dropzone.classList.add('drag-active');
        });
      });

      ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, e => {
          e.preventDefault();
          e.stopPropagation();
          dropzone.classList.remove('drag-active');
        });
      });

      dropzone.addEventListener('drop', e => {
        const dt = e.dataTransfer;
        if (dt && dt.files && dt.files.length > 0) {
          handleBatchImageUpload(dt.files);
        }
      });
    }

    if (DOM.localArtFileInput) {
      DOM.localArtFileInput.addEventListener('change', e => {
        handleBatchImageUpload(e.target.files);
        DOM.localArtFileInput.value = '';
      });
    }

    if (DOM.btnRefreshGallery) {
      DOM.btnRefreshGallery.addEventListener('click', loadGallery);
    }

    if (DOM.checkCycleUserUploads) {
      DOM.checkCycleUserUploads.checked = state.cycleUserUploads;
      DOM.checkCycleUserUploads.addEventListener('change', e => {
        state.cycleUserUploads = e.target.checked;
        localStorage.setItem('dhriti_cycle_user_uploads', e.target.checked);
      });
    }

    if (DOM.uploadTargetSetSelect) {
      DOM.uploadTargetSetSelect.addEventListener('change', (e) => {
        if (DOM.groupNewSetName) {
          DOM.groupNewSetName.style.display = e.target.value === '__new__' ? 'block' : 'none';
        }
      });
    }

    if (DOM.btnConfirmUploadSet) {
      DOM.btnConfirmUploadSet.addEventListener('click', confirmUploadIntoSet);
    }

    if (DOM.btnCancelUploadSet) {
      DOM.btnCancelUploadSet.addEventListener('click', () => {
        if (DOM.uploadSetModalOverlay) DOM.uploadSetModalOverlay.style.display = 'none';
        state.pendingUploadFiles = [];
      });
    }

    if (DOM.btnCloseUploadSetModal) {
      DOM.btnCloseUploadSetModal.addEventListener('click', () => {
        if (DOM.uploadSetModalOverlay) DOM.uploadSetModalOverlay.style.display = 'none';
        state.pendingUploadFiles = [];
      });
    }

    if (DOM.btnCloseInspector) {
      DOM.btnCloseInspector.addEventListener('click', () => {
        if (DOM.setInspectorOverlay) DOM.setInspectorOverlay.style.display = 'none';
        state.inspectedSetId = null;
      });
    }

    if (DOM.btnUseInspectedSet) {
      DOM.btnUseInspectedSet.addEventListener('click', () => {
        if (state.inspectedSetId) {
          activateSet(state.inspectedSetId);
          if (DOM.setInspectorOverlay) DOM.setInspectorOverlay.style.display = 'none';
          state.inspectedSetId = null;
        }
      });
    }

    if (DOM.btnAddArt && DOM.customArtUrl) {
      DOM.btnAddArt.addEventListener('click', () => {
        const url = DOM.customArtUrl.value.trim();
        if (!url) return;
        const customItem = {
          id: `url-${Date.now()}`,
          title: 'Custom Web Image',
          filename: 'web_image.jpg',
          url: url,
          size: 0
        };
        let targetSet = state.artSets.find(s => s.id === state.activeSetId);
        if (!targetSet || targetSet.isDefault) {
          targetSet = state.artSets.find(s => s.id === 'set-local-uploads');
          if (!targetSet) {
            targetSet = { id: 'set-local-uploads', name: 'My Local Uploads', isDefault: false, images: [] };
            state.artSets.push(targetSet);
          }
        }
        targetSet.images.unshift(customItem);
        saveArtSets();
        renderArtSets();
        setActiveArtwork(customItem);
        DOM.customArtUrl.value = '';
      });
    }
  }

  // --- Artwork & Quote Rotation ---
  function cycleArtwork() {
    const activeSet = state.artSets.find(s => s.id === state.activeSetId) || state.artSets[0];
    const pool = (activeSet && activeSet.images && activeSet.images.length > 0) ? activeSet.images : DEFAULT_ARTWORKS;
    state.currentArtIndex = (state.currentArtIndex + 1) % pool.length;
    setActiveArtwork(pool[state.currentArtIndex]);
  }

  function cycleQuote() {
    state.currentQuoteIndex = (state.currentQuoteIndex + 1) % state.quotes.length;
    const q = state.quotes[state.currentQuoteIndex];
    if (DOM.quoteText) DOM.quoteText.textContent = q.text;
    if (DOM.quoteAuthor) DOM.quoteAuthor.textContent = `— ${q.author}`;
  }

  // --- Wire Event Listeners ---
  function wireEvents() {
    // Mode toggles
    if (DOM.btnToggleMode) {
      DOM.btnToggleMode.addEventListener('click', () => {
        if (state.mode === 'picture') flipToDashboard();
        else returnToArt();
      });
    }

    if (DOM.btnReturnArt) {
      DOM.btnReturnArt.addEventListener('click', returnToArt);
    }

    if (DOM.btnNavArtMode) {
      DOM.btnNavArtMode.addEventListener('click', returnToArt);
    }

    if (DOM.sidebarBrand) {
      DOM.sidebarBrand.addEventListener('click', returnToArt);
    }

    if (DOM.modeBadge) {
      DOM.modeBadge.addEventListener('click', () => {
        if (state.mode === 'picture') flipToDashboard();
        else returnToArt();
      });
    }

    // Persistent header Pomodoro controls
    if (DOM.headerPomoToggle) {
      DOM.headerPomoToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        togglePomodoro();
      });
    }
    if (DOM.headerPomoPill) {
      DOM.headerPomoPill.addEventListener('click', () => {
        if (state.mode === 'picture') {
          // Flip the Pomodoro tile so user can see it right in Mode 1
          const pomoTile = document.querySelector('.tactile-tile[data-tile-id="1"]');
          if (pomoTile) pomoTile.classList.toggle('is-flipped');
        } else {
          showView('focus');
        }
      });
    }

    // Clicking tile in Mode 1 flips tile with audio and smoothly opens The Desk / target view in Dashboard
    DOM.tiles.forEach(tile => {
      tile.addEventListener('click', (e) => {
        e.stopPropagation();
        tile.classList.add('is-flipped');
        if (window.DhritiAudio) window.DhritiAudio.playFlipClick(0.7);
        const targetView = tile.getAttribute('data-view') || 'desk';
        setTimeout(() => {
          setMode('dashboard');
          showView(targetView);
        }, 180);
      });
    });

    // Theme toggle
    DOM.btnThemeToggle.addEventListener('click', () => {
      setTheme(state.theme === 'dark' ? 'light' : 'dark');
    });

    // Navigation items
    DOM.navItems.forEach(btn => {
      btn.addEventListener('click', () => {
        showView(btn.dataset.view);
      });
    });

    // Helper to add parked thought from Desk or Parking Lot view
    function addParkedThought(text, feedbackEl, inputEl) {
      const clean = (text || '').trim();
      if (!clean) return;
      state.parkingItems.unshift({ id: `park-${Date.now()}`, text: clean, age_days: 0, type: 'spark' });
      if (inputEl) inputEl.value = '';
      if (feedbackEl) {
        feedbackEl.textContent = 'Parked in curiosity mail slot for cold review.';
        setTimeout(() => { if (feedbackEl) feedbackEl.textContent = ''; }, 3000);
      }
      renderParkingTimeline();
      if (window.DhritiAudio && typeof window.DhritiAudio.playPebble === 'function') {
        window.DhritiAudio.playPebble(1.2);
      }
    }

    // Quick park input on The Desk
    if (DOM.btnQuickPark) {
      DOM.btnQuickPark.addEventListener('click', () => {
        addParkedThought(DOM.quickParkInput ? DOM.quickParkInput.value : '', DOM.quickParkFeedback, DOM.quickParkInput);
      });
    }
    if (DOM.quickParkInput) {
      DOM.quickParkInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          addParkedThought(DOM.quickParkInput.value, DOM.quickParkFeedback, DOM.quickParkInput);
        }
      });
    }

    // Add to Parking Lot in Curiosity Parking Lot view
    if (DOM.btnParkingViewAdd) {
      DOM.btnParkingViewAdd.addEventListener('click', () => {
        addParkedThought(DOM.parkingViewInput ? DOM.parkingViewInput.value : '', DOM.parkingViewFeedback, DOM.parkingViewInput);
      });
    }
    if (DOM.parkingViewInput) {
      DOM.parkingViewInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          addParkedThought(DOM.parkingViewInput.value, DOM.parkingViewFeedback, DOM.parkingViewInput);
        }
      });
    }

    // Focus engine
    if (DOM.btnFocusStart) DOM.btnFocusStart.addEventListener('click', togglePomodoro);
    if (DOM.btnFocusReset) DOM.btnFocusReset.addEventListener('click', resetPomodoro);

    DOM.focusPresetBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        DOM.focusPresetBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.pomodoro.mode = btn.dataset.preset;
        resetPomodoro();
      });
    });

    if (DOM.alarmSoundSelect) {
      DOM.alarmSoundSelect.addEventListener('change', e => {
        state.pomodoro.alarmSound = e.target.value;
      });
    }

    if (DOM.btnTestAlarm) {
      DOM.btnTestAlarm.addEventListener('click', () => {
        if (window.DhritiAudio) {
          window.DhritiAudio.playProceduralAlarm(state.pomodoro.alarmSound);
        }
      });
    }

    if (DOM.btnToggleNoise) {
      DOM.btnToggleNoise.addEventListener('click', () => {
        if (!window.DhritiAudio) return;
        if (state.pomodoro.noisePlaying) {
          window.DhritiAudio.stopNoise();
          state.pomodoro.noisePlaying = false;
          DOM.btnToggleNoise.textContent = 'Start Ambient Noise';
        } else {
          const type = document.querySelector('input[name="noise-type"]:checked').value;
          const vol = parseInt(DOM.sliderNoiseVol.value, 10) / 100;
          window.DhritiAudio.startNoise(type, vol);
          state.pomodoro.noisePlaying = true;
          DOM.btnToggleNoise.textContent = 'Stop Ambient Noise';
        }
      });
    }

    if (DOM.sliderNoiseVol) {
      DOM.sliderNoiseVol.addEventListener('input', e => {
        const v = parseInt(e.target.value, 10);
        DOM.valNoiseVol.textContent = `${v}%`;
        if (window.DhritiAudio) window.DhritiAudio.setNoiseVolume(v / 100);
      });
    }

    // Sidebar collapse / expand toggle
    const btnToggleSidebar = document.getElementById('btn-toggle-sidebar');
    const btnExpandSidebarTab = document.getElementById('btn-expand-sidebar-tab');
    function toggleSidebarCollapse() {
      if (!DOM.appShell) return;
      const isCollapsed = DOM.appShell.classList.toggle('sidebar-collapsed');
      if (btnExpandSidebarTab) {
        btnExpandSidebarTab.style.display = isCollapsed ? 'flex' : 'none';
      }
    }
    if (btnToggleSidebar) btnToggleSidebar.addEventListener('click', toggleSidebarCollapse);
    if (btnExpandSidebarTab) btnExpandSidebarTab.addEventListener('click', toggleSidebarCollapse);

    // Pick-Your-Poison modal
    if (DOM.btnOpenPoisonModal) DOM.btnOpenPoisonModal.addEventListener('click', openPickYourPoison);
    if (DOM.btnClosePoison) DOM.btnClosePoison.addEventListener('click', () => DOM.poisonModal.classList.remove('active'));

    // Life Mirror modal
    if (DOM.btnAddLifeAlt) DOM.btnAddLifeAlt.addEventListener('click', () => DOM.lifeModal.classList.add('active'));
    if (DOM.btnCloseLife) DOM.btnCloseLife.addEventListener('click', () => DOM.lifeModal.classList.remove('active'));
    if (DOM.btnSaveLifeAlt) {
      DOM.btnSaveLifeAlt.addEventListener('click', () => {
        const label = DOM.newLifeLabel.value.trim();
        if (!label) return;
        const newAlt = {
          id: `life-${Date.now()}`,
          label: label,
          category: DOM.newLifeCategory.value,
          duration: parseInt(DOM.newLifeDuration.value, 10)
        };
        state.lifeAlts.push(newAlt);
        try {
          localStorage.setItem('dhriti_life_alts', JSON.stringify(state.lifeAlts));
        } catch (e) {}
        if (window.DhritiBubbles && typeof window.DhritiBubbles.refreshFeed === 'function') {
          window.DhritiBubbles.refreshFeed();
        }
        DOM.newLifeLabel.value = '';
        DOM.lifeModal.classList.remove('active');
        renderLifeAlts();
      });
    }

    // Release Test Thought Bubble button
    const btnTestBubble = document.getElementById('btn-trigger-test-bubble');
    if (btnTestBubble) {
      btnTestBubble.addEventListener('click', () => {
        if (window.DhritiBubbles && typeof window.DhritiBubbles.spawnNow === 'function') {
          window.DhritiBubbles.spawnNow();
        }
      });
    }

    // Inline Add Topic Handler
    const btnAddTopic = document.getElementById('btn-add-topic');
    const inputTopicDom = document.getElementById('new-topic-domain');
    const inputTopicMin = document.getElementById('new-topic-minutes');
    if (btnAddTopic && inputTopicDom) {
      btnAddTopic.addEventListener('click', () => {
        const dom = (inputTopicDom.value || '').trim();
        if (!dom) return;
        const mins = parseInt(inputTopicMin ? inputTopicMin.value : '30', 10) || 30;
        state.topicTime.push({
          id: `top-${Date.now()}`,
          domain: dom,
          category: 'Stage (Active Focus)',
          duration_min: mins,
          is_stage: true
        });
        inputTopicDom.value = '';
        if (inputTopicMin) inputTopicMin.value = '';
        renderTopicBars();
        drawDonutChart();
      });
    }

    // Inline Add Contract Target Handler
    const btnAddTask = document.getElementById('btn-add-task');
    const inputTaskTitle = document.getElementById('new-task-title');
    if (btnAddTask && inputTaskTitle) {
      btnAddTask.addEventListener('click', () => {
        const t = (inputTaskTitle.value || '').trim();
        if (!t) return;
        state.activeTasks.push({
          id: `task-${Date.now()}`,
          title: t,
          units: 1.0,
          proof: 'machine_check',
          done: false
        });
        inputTaskTitle.value = '';
        renderContractTasks();
        if (window.DhritiAudio) window.DhritiAudio.playBell();
      });
    }

    // Inline Add Life Alternative Handler
    const btnQuickLife = document.getElementById('btn-quick-add-life');
    const inputQuickLife = document.getElementById('quick-life-label');
    if (btnQuickLife && inputQuickLife) {
      btnQuickLife.addEventListener('click', () => {
        const lbl = (inputQuickLife.value || '').trim();
        if (!lbl) return;
        state.lifeAlts.push({
          id: `life-${Date.now()}`,
          label: lbl,
          category: 'rest',
          duration: 15
        });
        try { localStorage.setItem('dhriti_life_alts', JSON.stringify(state.lifeAlts)); } catch (e) {}
        if (window.DhritiBubbles && typeof window.DhritiBubbles.refreshFeed === 'function') {
          window.DhritiBubbles.refreshFeed();
        }
        inputQuickLife.value = '';
        renderLifeAlts();
      });
    }

    // Lockdown modal
    if (DOM.btnLockdown) DOM.btnLockdown.addEventListener('click', () => DOM.lockdownModal.classList.add('active'));
    if (DOM.btnCloseLockdown) DOM.btnCloseLockdown.addEventListener('click', () => DOM.lockdownModal.classList.remove('active'));
    if (DOM.btnCancelLockdown) DOM.btnCancelLockdown.addEventListener('click', () => DOM.lockdownModal.classList.remove('active'));
    if (DOM.btnConfirmLockdown) {
      DOM.btnConfirmLockdown.addEventListener('click', () => {
        DOM.lockdownModal.classList.remove('active');
        alert('Daily Lockdown Engaged. Enforcement active until tomorrow morning.');
      });
    }

    // Guard test prompt
    if (DOM.btnEvalPrompt) DOM.btnEvalPrompt.addEventListener('click', evaluatePromptAlignment);

    // Settings overlay
    if (DOM.btnSettings) DOM.btnSettings.addEventListener('click', () => DOM.settingsOverlay.classList.add('active'));
    if (DOM.btnCloseSettings) DOM.btnCloseSettings.addEventListener('click', () => DOM.settingsOverlay.classList.remove('active'));

    // Settings Dials (Shell View) - Real-time synchronization
    if (DOM.shellSliderBrightness) {
      DOM.shellSliderBrightness.addEventListener('input', e => {
        state.underlay.brightness = parseInt(e.target.value, 10);
        updateUnderlayStyles();
      });
    }
    if (DOM.shellSliderBlur) {
      DOM.shellSliderBlur.addEventListener('input', e => {
        state.underlay.blur = parseInt(e.target.value, 10);
        updateUnderlayStyles();
      });
    }
    if (DOM.shellSliderOpacity) {
      DOM.shellSliderOpacity.addEventListener('input', e => {
        state.underlay.opacity = parseInt(e.target.value, 10);
        updateUnderlayStyles();
      });
    }

    // Settings Dials (Modal View) - Real-time synchronization
    if (DOM.modalSliderBrightness) {
      DOM.modalSliderBrightness.addEventListener('input', e => {
        state.underlay.brightness = parseInt(e.target.value, 10);
        updateUnderlayStyles();
      });
    }
    if (DOM.modalSliderBlur) {
      DOM.modalSliderBlur.addEventListener('input', e => {
        state.underlay.blur = parseInt(e.target.value, 10);
        updateUnderlayStyles();
      });
    }
    if (DOM.modalSliderOpacity) {
      DOM.modalSliderOpacity.addEventListener('input', e => {
        state.underlay.opacity = parseInt(e.target.value, 10);
        updateUnderlayStyles();
      });
    }

    // Theme Choosers (Both Shell and Modal)
    if (DOM.shellThemeCardDark) DOM.shellThemeCardDark.addEventListener('click', () => setTheme('dark'));
    if (DOM.shellThemeCardLight) DOM.shellThemeCardLight.addEventListener('click', () => setTheme('light'));
    if (DOM.modalThemeCardDark) DOM.modalThemeCardDark.addEventListener('click', () => setTheme('dark'));
    if (DOM.modalThemeCardLight) DOM.modalThemeCardLight.addEventListener('click', () => setTheme('light'));

    // Reset Wallpaper Underlay to Defaults
    if (DOM.btnResetUnderlayShell) DOM.btnResetUnderlayShell.addEventListener('click', resetUnderlayDefaults);
    if (DOM.btnResetUnderlayModal) DOM.btnResetUnderlayModal.addEventListener('click', resetUnderlayDefaults);

    // Triple-click gesture
    let clickCount = 0;
    let clickTimer = null;
    document.addEventListener('click', () => {
      clickCount++;
      if (clickCount === 1) {
        clickTimer = setTimeout(() => { clickCount = 0; }, 400);
      } else if (clickCount === 3) {
        clearTimeout(clickTimer);
        clickCount = 0;
        if (state.mode === 'picture') {
          cycleArtwork();
          cycleQuote();
        } else {
          returnToArt();
        }
      }
    });

    // Wire Play Configuration Panel (Niyam Vora Chimes Standards)
    wireChimesPlayPanel();

    // Wire Settings Tabs & Local Gallery Studio
    wireSettingsTabs();
    wireGalleryStudio();

    // Hourly quote rotation
    setInterval(cycleQuote, 3600000);
  }

  // --- Wire Chimes Play / Customise Configuration Panel ---
  function wireChimesPlayPanel() {
    const panel = document.getElementById('chimes-play-panel');
    const collapseBtn = document.getElementById('tp-collapse-toggle');
    const togglePanelBtn = document.getElementById('btn-toggle-play-panel');
    const titleBar = document.querySelector('.tp-title-bar');

    if (collapseBtn) {
      collapseBtn.addEventListener('click', e => {
        e.stopPropagation();
        if (panel) panel.style.display = 'none';
      });
    }

    if (titleBar) {
      titleBar.addEventListener('click', () => {
        if (!panel) return;
        panel.classList.toggle('is-collapsed');
      });
    }

    if (togglePanelBtn) {
      togglePanelBtn.addEventListener('click', () => {
        if (!panel) return;
        const isHidden = panel.style.display === 'none' || getComputedStyle(panel).display === 'none';
        if (isHidden) {
          panel.style.display = 'block';
          panel.classList.remove('is-collapsed');
        } else {
          panel.style.display = 'none';
        }
      });
    }

    // Two-way slider <-> number input binder
    function bindSliderNumPair(sliderId, numId, onUpdate) {
      const slider = document.getElementById(sliderId);
      const num = document.getElementById(numId);
      if (!slider || !num) return;

      slider.addEventListener('input', e => {
        num.value = e.target.value;
        onUpdate(e.target.value);
      });
      num.addEventListener('input', e => {
        slider.value = e.target.value;
        onUpdate(e.target.value);
      });
    }

    // Destination Country
    const countrySelect = document.getElementById('tp-country-select');
    if (countrySelect) {
      countrySelect.addEventListener('change', e => {
        if (window.DhritiChimes) window.DhritiChimes.setCountry(e.target.value);
      });
    }

    // Cloth Properties
    bindSliderNumPair('tp-slider-width', 'tp-num-width', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ width: parseFloat(val) });
    });
    bindSliderNumPair('tp-slider-height', 'tp-num-height', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ height: parseFloat(val) });
    });
    bindSliderNumPair('tp-slider-gridW', 'tp-num-gridW', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ gridW: parseInt(val, 10) });
    });
    bindSliderNumPair('tp-slider-gridH', 'tp-num-gridH', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ gridH: parseInt(val, 10) });
    });

    const btnRebuild = document.getElementById('tp-btn-rebuild');
    if (btnRebuild) {
      btnRebuild.addEventListener('click', () => {
        if (window.DhritiChimes) window.DhritiChimes.rebuild();
      });
    }

    // Motion & Sound Properties
    bindSliderNumPair('tp-slider-gravity', 'tp-num-gravity', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ gravity: parseFloat(val) });
    });
    bindSliderNumPair('tp-slider-damping', 'tp-num-damping', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ damping: parseFloat(val) });
    });
    bindSliderNumPair('tp-slider-iterations', 'tp-num-iterations', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ iterationsPerFrame: parseInt(val, 10) });
    });
    bindSliderNumPair('tp-slider-stretch', 'tp-num-stretch', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ stretchFactor: parseFloat(val) });
    });
    bindSliderNumPair('tp-slider-compress', 'tp-num-compress', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ compressFactor: parseFloat(val) });
    });
    bindSliderNumPair('tp-slider-mouseSize', 'tp-num-mouseSize', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ mouseSize: parseFloat(val) });
    });
    bindSliderNumPair('tp-slider-mouseStrength', 'tp-num-mouseStrength', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ mouseStrength: parseFloat(val) });
    });

    const checkChimes = document.getElementById('tp-check-chimes');
    if (checkChimes) {
      checkChimes.addEventListener('change', e => {
        if (window.DhritiChimes) window.DhritiChimes.updateConfig({ chimes: e.target.checked });
      });
    }

    bindSliderNumPair('tp-slider-volume', 'tp-num-volume', val => {
      if (window.DhritiChimes) window.DhritiChimes.updateConfig({ chimeVolume: parseFloat(val) });
    });

    const checkContain = document.getElementById('tp-check-contain');
    if (checkContain) {
      checkContain.addEventListener('change', e => {
        if (window.DhritiChimes) window.DhritiChimes.updateConfig({ contain: e.target.checked });
      });
    }
  }

  // --- Vidura Surfacing & Recall-Before-Reveal Protocol ---
  let currentRecallItem = null;

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function loadDailySurfacingCard() {
    try {
      const resp = await fetch('/api/vidura/surface');
      if (!resp.ok) return;
      const data = await resp.json();
      if (!data.ok || !data.card) {
        const promptEl = document.getElementById('vidura-prompt-text');
        if (promptEl) promptEl.textContent = 'All saved items reviewed! No pending decay items for today.';
        return;
      }
      currentRecallItem = data.card;
      const domainEl = document.getElementById('vidura-domain-pill');
      if (domainEl) domainEl.textContent = `Domain: ${data.card.domain || 'general'}`;
      const effortEl = document.getElementById('vidura-effort-pill');
      if (effortEl) effortEl.textContent = `Effort: ${data.card.effort || '30min'}`;
      const promptEl = document.getElementById('vidura-prompt-text');
      if (promptEl) {
        promptEl.textContent = `"${data.card.title}" — ${data.card.prompt}`;
      }
      const maskedView = document.getElementById('vidura-recall-masked-view');
      const revealedView = document.getElementById('vidura-recall-revealed-view');
      if (maskedView) maskedView.style.display = 'block';
      if (revealedView) revealedView.style.display = 'none';
    } catch (e) {
      console.warn('Vidura surfacing load notice:', e);
    }
  }

  async function submitViduraRecall(answer) {
    if (!currentRecallItem) return;
    try {
      const resp = await fetch('/api/vidura/recall', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: currentRecallItem.item_id, answer: answer || '' })
      });
      if (!resp.ok) return;
      const data = await resp.json();
      if (data.ok && data.result) {
        const maskedView = document.getElementById('vidura-recall-masked-view');
        const revealedView = document.getElementById('vidura-recall-revealed-view');
        if (maskedView) maskedView.style.display = 'none';
        if (revealedView) revealedView.style.display = 'block';

        const statusEl = document.getElementById('vidura-revealed-status');
        if (statusEl) {
          if (data.result.recalled) {
            statusEl.textContent = 'Recall Successful — Item Unlocked';
            statusEl.style.color = '#00b894';
          } else {
            statusEl.textContent = 'Recall Acknowledged (Decay Recorded) — Item Unlocked';
            statusEl.style.color = '#fdcb6e';
          }
        }
        const titleEl = document.getElementById('vidura-revealed-title');
        if (titleEl) titleEl.textContent = data.result.title;
        const descEl = document.getElementById('vidura-revealed-desc');
        if (descEl) descEl.textContent = data.result.description || 'Saved resource unlocked from Vidura archive.';
        const linkEl = document.getElementById('vidura-revealed-link');
        if (linkEl) linkEl.href = data.result.url;
        const metaEl = document.getElementById('vidura-revealed-meta');
        if (metaEl) {
          metaEl.textContent = `Source: ${data.result.source || 'vidura'} | Domain: ${data.result.facet_domain}`;
        }
      }
    } catch (e) {
      console.warn('Vidura recall error:', e);
    }
  }

  async function loadLifeInstruments() {
    try {
      const resp = await fetch('/api/vidura/instruments');
      if (!resp.ok) return;
      const data = await resp.json();
      if (!data.ok || !data.instruments) return;

      const container = document.getElementById('vidura-instruments-list');
      const badge = document.getElementById('badge-instrument-count');
      if (badge) badge.textContent = `${data.count} Interactive Tools`;
      if (!container) return;

      container.innerHTML = '';
      data.instruments.forEach(inst => {
        const card = document.createElement('div');
        card.className = 'alt-bubble-chip';
        card.style.flexDirection = 'column';
        card.style.alignItems = 'flex-start';
        card.style.gap = '6px';
        card.style.padding = '10px 14px';
        card.style.borderRadius = '10px';

        card.innerHTML = `
          <div style="font-weight: 600; font-size: 13px; color: var(--text-primary); line-height: 1.3;">
            ${escapeHtml(inst.title)}
          </div>
          <div style="font-size: 11px; opacity: 0.7; color: var(--text-secondary);">
            Domain: ${escapeHtml(inst.facet_domain || 'craft')} | Effort: ${escapeHtml(inst.facet_effort || 'tool')}
          </div>
          <div style="display: flex; gap: 8px; margin-top: 4px; width: 100%;">
            <a href="${escapeHtml(inst.url)}" target="_blank" class="btn-primary btn-sm" style="text-decoration: none; padding: 3px 8px; font-size: 11px;">
              Launch Tool
            </a>
            <button type="button" class="btn-sec btn-sm btn-log-inst" style="padding: 3px 8px; font-size: 11px;">
              Log Practice
            </button>
          </div>
        `;

        const logBtn = card.querySelector('.btn-log-inst');
        if (logBtn) {
          logBtn.addEventListener('click', () => {
            logBtn.textContent = 'Logged!';
            logBtn.disabled = true;
            logBtn.style.opacity = '0.6';
          });
        }
        container.appendChild(card);
      });
    } catch (e) {
      console.warn('Instruments load notice:', e);
    }
  }

  function wireViduraControls() {
    const btnUnlock = document.getElementById('btn-vidura-unlock');
    const input = document.getElementById('vidura-recall-input');
    if (btnUnlock && input) {
      btnUnlock.addEventListener('click', () => {
        submitViduraRecall(input.value);
      });
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitViduraRecall(input.value);
      });
    }

    const btnForgot = document.getElementById('btn-vidura-forgot');
    if (btnForgot) {
      btnForgot.addEventListener('click', () => {
        submitViduraRecall('forgot');
      });
    }

    const btnSkip = document.getElementById('btn-vidura-skip');
    if (btnSkip) {
      btnSkip.addEventListener('click', () => {
        const card = document.getElementById('card-vidura-recall');
        if (card) card.style.opacity = '0.4';
      });
    }

    // YouTube Sync buttons
    const syncButtons = [
      document.getElementById('btn-sync-youtube'),
      document.getElementById('btn-sync-youtube-top')
    ];
    const syncStatus = document.getElementById('sync-youtube-status');

    syncButtons.forEach(btn => {
      if (!btn) return;
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        const originalText = btn.textContent;
        btn.textContent = 'Syncing Queue...';
        if (syncStatus) syncStatus.textContent = 'Executing Vidura YouTube sync in background...';

        try {
          const resp = await fetch('/api/vidura/sync', { method: 'POST' });
          const res = await resp.json();
          if (syncStatus) syncStatus.textContent = res.message || 'Sync started in background.';
          setTimeout(() => {
            btn.disabled = false;
            btn.textContent = originalText;
            loadDailySurfacingCard();
            loadLifeInstruments();
          }, 3500);
        } catch (err) {
          if (syncStatus) syncStatus.textContent = 'Failed to trigger sync: ' + err;
          btn.disabled = false;
          btn.textContent = originalText;
        }
      });
    });
  }

  // --- Initialization ---
  function init() {
    window.DhritiState = state;
    initDOM();
    wireEvents();
    wireViduraControls();
    updateTimerDisplay();
    updateUnderlayStyles();
    loadGallery();
    drawDonutChart();
    renderParkingTimeline();
    renderLifeAlts();
    loadDailySurfacingCard();
    loadLifeInstruments();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
