/**
 * Dhriti Suspended Poem Chimes & Cloth Engine (v0.7.0+)
 * Fully modeled on Niyam Vora's Chimes (niyamvora.github.io/chimes)
 *
 * Implements:
 * 1. High-performance Verlet cloth physics with offscreen canvas character caching (solid 60-120 FPS).
 * 2. Country-tuned acoustic bell chime strikes with speed/proximity modulation.
 * 3. Ideal standard parameters matching Niyam Vora's Play configuration pane:
 *    - Width: 492, Height: 468, Columns: 36, Rows: 40
 *    - Gravity: 0.20, Damping: 0.990, Precision: 5
 *    - Stretch: 1.10, Compress: 0.02, Touch radius: 5000, Touch force: 4
 * 4. Silky smooth cursor brushing with Hermite smoothstep radial deflection.
 * 5. Asymmetrically staggered poem stanza cards attached to chains with grab & drag physics.
 * 6. Live Rebuild & Configuration Controls.
 */

(() => {
  "use strict";

  // --- Math Utilities ---
  function smoothstep(edge0, edge1, x) {
    const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
    return t * t * (3 - 2 * t);
  }

  function getPointID(row, col, gridH) {
    return col * gridH + row;
  }

  class Vec2 {
    constructor(x = 0, y = 0) {
      this.reset(x, y);
    }
    zero() {
      this.reset(0, 0);
    }
    reset(x = 0, y = 0) {
      this.x = x;
      this.y = y;
    }
    clone() {
      return new Vec2(this.x, this.y);
    }
    add(v) {
      this.x += v.x;
      this.y += v.y;
      return this;
    }
    subtract(v) {
      this.x -= v.x;
      this.y -= v.y;
      return this;
    }
    subtractNew(v) {
      return this.clone().subtract(v);
    }
    scale(scalar) {
      this.x *= scalar;
      this.y *= scalar;
      return this;
    }
    get lengthSquared() {
      return this.x ** 2 + this.y ** 2;
    }
    get length() {
      return Math.hypot(this.x, this.y);
    }
    get angle() {
      return Math.atan2(this.y, this.x);
    }
  }

  // --- Ideal Standard Configuration (Spacious, Roomy Draped Installation) ---
  const CONFIG = {
    width: 1080,
    height: 680,
    gridW: 32,
    gridH: 32,
    gravity: 0.20,
    damping: 0.990,
    iterationsPerFrame: 5,
    stretchFactor: 1.10,
    compressFactor: 0.02,
    mouseSize: 5000,
    mouseStrength: 4,
    chimes: true,
    chimeVolume: 0.28,
    contain: false,
    country: "china"
  };

  // --- Physical Particle ---
  class Particle {
    constructor({ x, y, pinned = false, id = 0, char = "", stanzaIdx = -1, isStanzaAnchor = false } = {}) {
      this.pos = new Vec2(x, y);
      this.oldPos = new Vec2(x, y);
      this.velocity = new Vec2();
      this.acceleration = new Vec2();
      this.pinned = pinned;
      this.originalPinnedState = pinned;
      this.id = id;
      this.char = char;
      this.stanzaIdx = stanzaIdx;
      this.isStanzaAnchor = isStanzaAnchor;
      this.gravityVec = new Vec2();
      this.downConstraint = null;
    }

    contain(w, h) {
      if (this.pinned) return;
      const radius = 4;
      const minX = -originX + radius;
      const maxX = (canvasW - originX) - radius;
      const minY = -originY + radius;
      const maxY = (canvasH - originY) - radius;

      if (this.pos.x < minX) {
        this.pos.x = minX;
        this.oldPos.x = this.pos.x + Math.abs(this.oldPos.x - this.pos.x) * 0.8;
      } else if (this.pos.x > maxX) {
        this.pos.x = maxX;
        this.oldPos.x = this.pos.x - Math.abs(this.oldPos.x - this.pos.x) * 0.8;
      }
      if (this.pos.y < minY) {
        this.pos.y = minY;
        this.oldPos.y = this.pos.y + Math.abs(this.oldPos.y - this.pos.y) * 0.8;
      } else if (this.pos.y > maxY) {
        this.pos.y = maxY;
        this.oldPos.y = this.pos.y - Math.abs(this.oldPos.y - this.pos.y) * 0.8;
      }
    }

    update(delta) {
      if (this.pinned) {
        this.acceleration.zero();
        return;
      }
      this.velocity.reset(
        (this.pos.x - this.oldPos.x) * CONFIG.damping,
        (this.pos.y - this.oldPos.y) * CONFIG.damping
      );
      this.oldPos.reset(this.pos.x, this.pos.y);

      const dd = delta ** 2;
      this.gravityVec.reset(0, CONFIG.gravity / dd);
      this.applyForce(this.gravityVec);

      this.pos.x += this.velocity.x + this.acceleration.x * dd;
      this.pos.y += this.velocity.y + this.acceleration.y * dd;
      this.acceleration.reset();

      if (CONFIG.contain) {
        this.contain(canvasW, canvasH);
      }
    }

    applyForce(v) {
      this.acceleration.add(v);
    }
  }

  // --- Elastic Constraint with Asymmetric Limits ---
  class Constraint {
    constructor({ p1, p2, length, id, compressFactor, stretchFactor, isSpacer = false }) {
      this.p1 = p1;
      this.p2 = p2;
      this.length = length;
      this.id = id;
      this.isSpacer = isSpacer;
      this.compressFactor = compressFactor;
      this.stretchFactor = stretchFactor;
      this.minLength = length * compressFactor;
      this.maxLength = length * stretchFactor;
    }

    solve() {
      const dx = this.p2.pos.x - this.p1.pos.x;
      const dy = this.p2.pos.y - this.p1.pos.y;
      const distance = Math.hypot(dx, dy);
      if (distance === 0) return;

      let targetLength = this.length;
      if (distance < this.minLength) targetLength = this.minLength;
      else if (distance > this.maxLength) targetLength = this.maxLength;
      else return;

      const percent = (targetLength - distance) / distance / 2;
      const offsetX = dx * percent;
      const offsetY = dy * percent;

      if (!this.p1.pinned) {
        this.p1.pos.x -= offsetX;
        this.p1.pos.y -= offsetY;
      }
      if (!this.p2.pinned) {
        this.p2.pos.x += offsetX;
        this.p2.pos.y += offsetY;
      }
    }
  }

  // --- Default Cultural Doorway Poems & Stanzas ---
  const DEFAULT_POEM = {
    title: "Where the Mind is Without Fear",
    author: "Rabindranath Tagore",
    stanzas: [
      [
        "Where the mind is without fear",
        "and the head is held high;",
        "Where knowledge is free;"
      ],
      [
        "Where the world has not been",
        "broken up into fragments",
        "By narrow domestic walls;"
      ],
      [
        "Where words come out from",
        "the depth of truth;",
        "Where tireless striving",
        "stretches its arms towards perfection;"
      ],
      [
        "Where the clear stream of reason",
        "has not lost its way",
        "Into the dreary desert sand of dead habit;"
      ],
      [
        "Where the mind is led forward",
        "by thee into ever-widening",
        "thought and action;"
      ],
      [
        "Into that heaven of freedom,",
        "my Father, let my country awake."
      ]
    ]
  };

  // Cultural poetic chimes glyphs (clean, elegant, no noisy arcade digits)
  const GLYPH_CHARS = "✦◊◈◇•⚓WMFHKTRDPSAELN";

  // Harmonious painting-matched bead styles & palettes (muted gold, rose, verdigris, slate, parchment)
  const BEAD_SHAPES = ["circle", "rhombus", "star", "hexagon", "triangle", "octagon"];
  const BEAD_PALETTES = [
    { fill: "#241f1a", stroke: "#d8b46a", text: "#f6eccb" }, // Muted Antique Gold
    { fill: "#271c21", stroke: "#c76b7a", text: "#fce9ed" }, // Dusty Rose
    { fill: "#1a2520", stroke: "#7fa08a", text: "#e8f2ec" }, // Sage Verdigris
    { fill: "#1a1f2e", stroke: "#8fa3d1", text: "#e4ebf8" }, // Slate Periwinkle
    { fill: "#292621", stroke: "#e0d3b8", text: "#ffffff" }  // Warm Parchment
  ];

  // --- Engine State & Cloth System ---
  let canvas = null;
  let ctx = null;
  let particles = [];
  let constraints = [];
  let charCanvases = {};
  let stanzaCanvases = [];
  let currentPoem = DEFAULT_POEM;
  let grabbedParticle = null;
  let isSimulating = false;
  let lastSim = performance.now();
  let simRaf = null;
  let dpr = 1;

  // Staggered stanza anchor definitions (organic non-uniform heights)
  let activeStanzaAnchors = [];

  // Coordinate transforms
  let canvasW = 1280;
  let canvasH = 780;
  let originX = 0;
  let originY = 30;

  const mousePos = new Vec2();
  const chimeRadiusSq = 55 * 55;
  const grabRadius = 36;

  // Helper: Draw geometric polygon on offscreen canvas
  function drawPolygon(octx, x, y, radius, sides, startAngle = -Math.PI / 2) {
    octx.beginPath();
    for (let i = 0; i < sides; i++) {
      const a = startAngle + (i * 2 * Math.PI) / sides;
      const px = x + radius * Math.cos(a);
      const py = y + radius * Math.sin(a);
      if (i === 0) octx.moveTo(px, py);
      else octx.lineTo(px, py);
    }
    octx.closePath();
  }

  // Helper: Draw star shape
  function drawStar(octx, cx, cy, spikes, outerRadius, innerRadius) {
    let rot = (Math.PI / 2) * 3;
    let x = cx;
    let y = cy;
    const step = Math.PI / spikes;

    octx.beginPath();
    octx.moveTo(cx, cy - outerRadius);
    for (let i = 0; i < spikes; i++) {
      x = cx + Math.cos(rot) * outerRadius;
      y = cy + Math.sin(rot) * outerRadius;
      octx.lineTo(x, y);
      rot += step;

      x = cx + Math.cos(rot) * innerRadius;
      y = cy + Math.sin(rot) * innerRadius;
      octx.lineTo(x, y);
      rot += step;
    }
    octx.lineTo(cx, cy - outerRadius);
    octx.closePath();
  }

  // --- Offscreen Pre-rendering Cache (Key to 60-120 FPS!) ---
  function preRenderAssets() {
    dpr = window.devicePixelRatio || 1;
    charCanvases = {};

    // 1. Pre-render multi-shape bead glyphs once with DPR scaling
    const fontSize = 13;
    const size = Math.ceil(fontSize * 1.6);
    const charsToCache = new Set(GLYPH_CHARS.split(""));

    let beadIdx = 0;
    charsToCache.forEach(ch => {
      const shape = BEAD_SHAPES[beadIdx % BEAD_SHAPES.length];
      const pal = BEAD_PALETTES[beadIdx % BEAD_PALETTES.length];
      beadIdx++;

      const off = document.createElement("canvas");
      off.width = Math.ceil(size * dpr);
      off.height = Math.ceil(size * dpr);
      off._size = size;
      const octx = off.getContext("2d");
      octx.setTransform(dpr, 0, 0, dpr, 0, 0);

      const center = size / 2;
      const radius = size * 0.44;

      // Draw distinctive bead geometry
      if (shape === "circle") {
        octx.beginPath();
        octx.arc(center, center, radius, 0, Math.PI * 2);
      } else if (shape === "rhombus") {
        octx.beginPath();
        octx.moveTo(center, center - radius);
        octx.lineTo(center + radius * 0.85, center);
        octx.lineTo(center, center + radius);
        octx.lineTo(center - radius * 0.85, center);
        octx.closePath();
      } else if (shape === "star") {
        drawStar(octx, center, center, 4, radius, radius * 0.45);
      } else if (shape === "hexagon") {
        drawPolygon(octx, center, center, radius, 6);
      } else if (shape === "triangle") {
        drawPolygon(octx, center, center, radius, 3);
      } else if (shape === "octagon") {
        drawPolygon(octx, center, center, radius, 8);
      }

      octx.fillStyle = pal.fill;
      octx.fill();
      octx.lineWidth = 1.2;
      octx.strokeStyle = pal.stroke;
      octx.stroke();

      // Render center glyph
      octx.font = `600 ${fontSize * 0.72}px ui-monospace, SFMono-Regular, monospace`;
      octx.textAlign = "center";
      octx.textBaseline = "middle";
      octx.fillStyle = pal.text;
      octx.fillText(ch, center, center + 0.5);

      charCanvases[ch] = off;
    });

    // 2. Pre-render poem stanza cards with dynamic width sized to text, Arvo bold-italic, and corner numeral
    const measureCanvas = document.createElement("canvas");
    const measureCtx = measureCanvas.getContext("2d");
    measureCtx.font = '700 italic 14px "Arvo", Georgia, serif';

    stanzaCanvases = currentPoem.stanzas.map((lines, sIdx) => {
      let maxLineWidth = 0;
      lines.forEach(line => {
        const textWidth = measureCtx.measureText(line).width;
        if (textWidth > maxLineWidth) maxLineWidth = textWidth;
      });

      // Card width sized according to text length + comfortable horizontal margins (no text cut off)
      const cardW = Math.max(280, Math.ceil(maxLineWidth + 46));
      const cardH = 46 + lines.length * 26;
      const off = document.createElement("canvas");
      off.width = Math.ceil(cardW * dpr);
      off.height = Math.ceil(cardH * dpr);
      off._cardW = cardW;
      off._cardH = cardH;

      const octx = off.getContext("2d");
      octx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Card Background (Translucent Deep Slate with Muted Gold Border)
      const r = 14;
      octx.beginPath();
      octx.moveTo(r, 0);
      octx.lineTo(cardW - r, 0);
      octx.quadraticCurveTo(cardW, 0, cardW, r);
      octx.lineTo(cardW, cardH - r);
      octx.quadraticCurveTo(cardW, cardH, cardW - r, cardH);
      octx.lineTo(r, cardH);
      octx.quadraticCurveTo(0, cardH, 0, cardH - r);
      octx.lineTo(0, r);
      octx.quadraticCurveTo(0, 0, r, 0);
      octx.closePath();

      octx.fillStyle = "rgba(16, 20, 34, 0.94)";
      octx.fill();
      octx.lineWidth = 1.5;
      octx.strokeStyle = "rgba(216, 180, 106, 0.50)";
      octx.stroke();

      // Stanza Lines in Arvo bold-italic (User's preferred combination!)
      octx.font = '700 italic 14px "Arvo", Georgia, serif';
      octx.fillStyle = '#fdfcf8';
      octx.textAlign = 'left';
      lines.forEach((line, lIdx) => {
        octx.fillText(line, 20, 28 + lIdx * 26);
      });

      // Single number at bottom-right end corner (1, 2, 3...)
      octx.font = '700 13px "Poiret One", sans-serif';
      octx.fillStyle = 'rgba(216, 180, 106, 0.75)';
      octx.textAlign = 'right';
      octx.fillText(`${sIdx + 1}`, cardW - 16, cardH - 12);

      return off;
    });
  }

  // --- Cloth & Stanza Network Builder ---
  function buildCloth() {
    if (!canvas) return;

    // Center cloth horizontally on canvas
    originX = Math.max(20, (canvasW - CONFIG.width) / 2);
    originY = 25;

    particles = [];
    constraints = [];
    activeStanzaAnchors = [];

    const gridW = CONFIG.gridW;
    const gridH = CONFIG.gridH;
    const cellWidth = CONFIG.width / (gridW - 1);
    const cellHeight = CONFIG.height / (gridH - 1);

    // Staggered Stanza Column Mapping:
    // Stanzas are distributed across 3 distinct columns with ample spacing
    const stanzaConfigs = [
      { col: 4,  startRow: 3,  stanzaIdx: 0 },
      { col: 4,  startRow: 15, stanzaIdx: 1 },
      { col: 15, startRow: 5,  stanzaIdx: 2 },
      { col: 15, startRow: 17, stanzaIdx: 3 },
      { col: 26, startRow: 4,  stanzaIdx: 4 },
      { col: 26, startRow: 16, stanzaIdx: 5 }
    ];

    // 1. Create Particles
    for (let i = 0; i < gridW; i++) {
      for (let j = 0; j < gridH; j++) {
        const x = i * cellWidth;
        const y = j * cellHeight;
        const id = getPointID(j, i, gridH);
        const pinned = j === 0;

        // Bead glyph
        const char = GLYPH_CHARS[(i * 7 + j * 3) % GLYPH_CHARS.length];

        // Check if particle is a stanza anchor
        let stanzaIdx = -1;
        let isAnchor = false;
        const matched = stanzaConfigs.find(s => s.col === i && s.startRow === j);
        if (matched) {
          stanzaIdx = matched.stanzaIdx;
          isAnchor = true;
        }

        const p = new Particle({
          x,
          y,
          pinned,
          id,
          char,
          stanzaIdx,
          isStanzaAnchor: isAnchor
        });
        particles.push(p);
        if (isAnchor) activeStanzaAnchors.push(p);
      }
    }

    // 2. Create Constraints (Vertical Strings & Horizontal Spacers)
    for (let i = 0; i < gridW; i++) {
      for (let j = 0; j < gridH; j++) {
        const id = getPointID(j, i, gridH);
        const p = particles[id];

        // Vertical constraint along string
        if (j < gridH - 1) {
          const bottomP = particles[getPointID(j + 1, i, gridH)];
          const constraint = new Constraint({
            p1: p,
            p2: bottomP,
            length: cellHeight,
            id: id + gridW * gridH,
            compressFactor: CONFIG.compressFactor,
            stretchFactor: CONFIG.stretchFactor
          });
          constraints.push(constraint);
          p.downConstraint = constraint;
        }

        // Horizontal spacer constraint between adjacent strings
        if (i < gridW - 1) {
          const rightP = particles[getPointID(j, i + 1, gridH)];
          constraints.push(
            new Constraint({
              p1: p,
              p2: rightP,
              length: cellWidth,
              id: id + gridW * gridH * 2,
              compressFactor: 0.60,
              stretchFactor: 4.0,
              isSpacer: true
            })
          );
        }
      }
    }

    // 3. Pre-settle warm up relaxation (70 frames) so strings start at resting hang
    for (let f = 0; f < 70; f++) {
      particles.forEach(p => p.update(16));
      for (let k = 0; k < CONFIG.iterationsPerFrame; k++) {
        for (let m = 0; m < constraints.length; m++) constraints[m].solve();
      }
    }
  }

  // Occlusion Helper: Prevent beads from obscuring stanza text
  function isCoveredByStanza(p) {
    if (p.isStanzaAnchor) return false;
    for (let i = 0; i < activeStanzaAnchors.length; i++) {
      const anchor = activeStanzaAnchors[i];
      const card = stanzaCanvases[anchor.stanzaIdx];
      if (!card) continue;
      const cardW = card._cardW;
      const cardH = card._cardH;
      const minX = anchor.pos.x - cardW / 2 - 4;
      const maxX = anchor.pos.x + cardW / 2 + 4;
      const minY = anchor.pos.y - 4;
      const maxY = anchor.pos.y + cardH + 4;
      if (p.pos.x >= minX && p.pos.x <= maxX && p.pos.y >= minY && p.pos.y <= maxY) {
        return true;
      }
    }
    return false;
  }

  // --- Rendering Loop (Zero allocation, high-DPI blit) ---
  function draw() {
    if (!ctx) return;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, canvasW, canvasH);

    // 1. Draw Bead Strings (Skip beads occluded behind stanza cards)
    particles.forEach(p => {
      if (isCoveredByStanza(p)) return;

      const img = charCanvases[p.char];
      if (!img) return;

      let cos = 1;
      let sin = 0;
      const constraint = p.downConstraint;
      if (constraint) {
        const dx = constraint.p2.pos.x - constraint.p1.pos.x;
        const dy = constraint.p2.pos.y - constraint.p1.pos.y;
        const angle = Math.atan2(dy, dx) - Math.PI / 2;
        cos = Math.cos(angle);
        sin = Math.sin(angle);
      }

      const size = img._size;
      const half = size / 2;
      const x = p.pos.x + originX;
      const y = p.pos.y + originY;

      ctx.setTransform(
        cos * dpr,
        sin * dpr,
        -sin * dpr,
        cos * dpr,
        x * dpr,
        y * dpr
      );
      ctx.drawImage(img, -half, -half, size, size);
    });

    // 2. Draw Suspended Stanza Cards (Anchored to Stanza Particles)
    activeStanzaAnchors.forEach(p => {
      if (!p.isStanzaAnchor || p.stanzaIdx < 0) return;
      const cardCanvas = stanzaCanvases[p.stanzaIdx];
      if (!cardCanvas) return;

      let cos = 1;
      let sin = 0;
      const constraint = p.downConstraint;
      if (constraint) {
        const dx = constraint.p2.pos.x - constraint.p1.pos.x;
        const dy = constraint.p2.pos.y - constraint.p1.pos.y;
        const angle = (Math.atan2(dy, dx) - Math.PI / 2) * 0.40; // Gentle tilt
        cos = Math.cos(angle);
        sin = Math.sin(angle);
      }

      const cardW = cardCanvas._cardW;
      const cardH = cardCanvas._cardH;
      const x = p.pos.x + originX;
      const y = p.pos.y + originY;

      ctx.setTransform(
        cos * dpr,
        sin * dpr,
        -sin * dpr,
        cos * dpr,
        x * dpr,
        y * dpr
      );
      ctx.drawImage(cardCanvas, -cardW / 2, 0, cardW, cardH);
    });
  }

  // --- Physics Step ---
  function tick(dt) {
    particles.forEach(p => p.update(dt));
    for (let k = 0; k < CONFIG.iterationsPerFrame; k++) {
      for (let m = 0; m < constraints.length; m++) constraints[m].solve();
    }
    draw();
  }

  function simLoop(now) {
    if (!isSimulating) return;
    const dt = Math.min(32, Math.max(1, now - lastSim));
    lastSim = now;
    tick(dt);
    simRaf = requestAnimationFrame(simLoop);
  }

  // --- Coordinate Mapping & Mouse/Touch Interaction ---
  function localPoint(clientX, clientY) {
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return null;
    return {
      x: ((clientX - rect.left) / rect.width) * canvasW - originX,
      y: ((clientY - rect.top) / rect.height) * canvasH - originY
    };
  }

  function brush(clientX, clientY, { chime = true } = {}) {
    const pt = localPoint(clientX, clientY);
    if (!pt) return;
    mousePos.reset(pt.x, pt.y);

    let nearest = null;
    let nearestLs = Infinity;

    for (const p of particles) {
      const diff = mousePos.subtractNew(p.pos);
      const ls = diff.lengthSquared;
      if (ls < CONFIG.mouseSize) {
        const a = diff.angle - Math.PI;
        const strength =
          (smoothstep(CONFIG.mouseSize, -2000, ls) * CONFIG.mouseStrength) / 300;
        p.applyForce(new Vec2(Math.cos(a) * strength, Math.sin(a) * strength));
      }
      if (chime && ls < chimeRadiusSq && ls < nearestLs) {
        nearest = p;
        nearestLs = ls;
      }
    }

    if (chime && nearest && CONFIG.chimes && window.DhritiAudio?.chimes) {
      const closeness = 1 - nearestLs / chimeRadiusSq;
      window.DhritiAudio.chimes.setCountry(CONFIG.country);
      window.DhritiAudio.chimes.strike({
        x: pt.x,
        y: pt.y,
        particle: nearest,
        gridW: CONFIG.gridW,
        intensity: 0.2 + closeness * 0.7
      });
    }
  }

  // --- Pointer Event Handlers (Brushing + Dragging) ---
  function onPointerDown(e) {
    const pt = localPoint(e.clientX, e.clientY);
    if (!pt) return;

    mousePos.reset(pt.x, pt.y);

    // Check if clicked near any particle or stanza card
    for (const p of particles) {
      const dist = mousePos.subtractNew(p.pos).length;
      if (dist < grabRadius) {
        // Dragging is permitted ONLY for chains with stanzas (loose beaded chains move via smooth hover brushing)
        const isStanzaChain = p.isStanzaAnchor || p.stanzaIdx >= 0 || activeStanzaAnchors.some(a => Math.abs(a.pos.x - p.pos.x) < 14);
        if (isStanzaChain) {
          grabbedParticle = p;
          grabbedParticle.originalPinnedState = p.pinned;
          grabbedParticle.pinned = true;
        }

        if (CONFIG.chimes && window.DhritiAudio?.chimes) {
          window.DhritiAudio.chimes.setCountry(CONFIG.country);
          window.DhritiAudio.chimes.strike({
            x: pt.x,
            y: pt.y,
            particle: p,
            gridW: CONFIG.gridW,
            intensity: 0.85,
            force: true
          });
        }
        break;
      }
    }
  }

  function onPointerMove(e) {
    const pt = localPoint(e.clientX, e.clientY);
    if (!pt) return;

    if (grabbedParticle) {
      grabbedParticle.pos.reset(pt.x, pt.y);
      grabbedParticle.oldPos.reset(pt.x, pt.y);
    }

    brush(e.clientX, e.clientY, { chime: true });
  }

  function onPointerUp() {
    if (grabbedParticle) {
      grabbedParticle.pinned = grabbedParticle.originalPinnedState;
      grabbedParticle = null;
    }
  }

  // --- Canvas Resizing ---
  function resizeCanvas() {
    if (!canvas) return;
    const container = canvas.parentElement;
    if (!container) return;

    canvasW = container.clientWidth || window.innerWidth || 1400;
    canvasH = Math.max(container.clientHeight || 0, Math.ceil(window.innerHeight * 1.30), 1350);
    dpr = window.devicePixelRatio || 1;

    canvas.width = Math.ceil(canvasW * dpr);
    canvas.height = Math.ceil(canvasH * dpr);
    canvas.style.width = `${canvasW}px`;
    canvas.style.height = `${canvasH}px`;

    originX = Math.max(20, (canvasW - CONFIG.width) / 2);
    originY = 25;

    preRenderAssets();
    buildCloth();
  }

  // --- Public Engine Controller ---
  function initEngine() {
    canvas = document.getElementById("chimes-canvas");
    if (!canvas) return;
    ctx = canvas.getContext("2d");

    resizeCanvas();
    window.addEventListener("resize", resizeCanvas);

    canvas.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);

    isSimulating = true;
    lastSim = performance.now();
    if (simRaf) cancelAnimationFrame(simRaf);
    simRaf = requestAnimationFrame(simLoop);
  }

  function updateConfig(newOpts = {}) {
    Object.assign(CONFIG, newOpts);
    if (CONFIG.chimeVolume != null && window.DhritiAudio?.chimes) {
      window.DhritiAudio.chimes.setVolume(CONFIG.chimeVolume);
    }
  }

  function rebuild() {
    preRenderAssets();
    buildCloth();
  }

  function setPoem(poemData) {
    if (poemData && poemData.stanzas) {
      currentPoem = poemData;
      rebuild();
    }
  }

  function setCountry(countryId) {
    CONFIG.country = countryId;
    if (window.DhritiAudio?.chimes) {
      window.DhritiAudio.chimes.setCountry(countryId);
    }
  }

  // Auto-init on load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initEngine);
  } else {
    initEngine();
  }

  // Expose to window.DhritiChimes
  window.DhritiChimes = {
    CONFIG,
    updateConfig,
    rebuild,
    setPoem,
    setCountry,
    brush
  };

})();
