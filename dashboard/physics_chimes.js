/**
 * Dhriti Chimes Physics & Interactive Poem Installation
 * Inspired by Niyam Vora's Chimes (niyamvora.github.io/chimes).
 *
 * Implements:
 * 1. Cultural doorway curtain with multi-color, multi-shape beaded strings
 *    (Sphere, Star, Triangle, Hexagon, Octagon, Rhombus with specular shine or matte)
 * 2. Silky, smooth cursor hover interaction that parts doorway curtain strings
 *    with authentic Verlet physics and synthesized Akebono chimes
 * 3. Asymmetric, organically staggered Stanza Chains where adjacent poem blocks
 *    sit at different, non-uniform heights
 * 4. Dedicated drag-and-drop physics exclusively for Stanza Chains and cards
 */
(() => {
  "use strict";

  const BEAD_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789✦◊◈⚓⏣§¶";

  const BEAD_SHAPES = ["sphere", "star", "triangle", "hexagon", "octagon", "rhombus"];

  const BEAD_PALETTES = [
    { name: "cyan",     main: "#06b6d4", dark: "#0e7490", light: "#a5f3fc" },
    { name: "emerald",  main: "#10b981", dark: "#047857", light: "#a7f3d0" },
    { name: "amber",    main: "#f59e0b", dark: "#b45309", light: "#fde68a" },
    { name: "rose",     main: "#f43f5e", dark: "#be123c", light: "#fecdd3" },
    { name: "amethyst", main: "#8b5cf6", dark: "#6d28d9", light: "#ddd6fe" },
    { name: "sapphire", main: "#3b82f6", dark: "#1d4ed8", light: "#bfdbfe" },
    { name: "gold",     main: "#eab308", dark: "#a16207", light: "#fef08a" },
    { name: "coral",    main: "#fb7185", dark: "#9f1239", light: "#ffe4e6" },
    { name: "pearl",    main: "#e2e8f0", dark: "#64748b", light: "#ffffff" },
    { name: "bronze",   main: "#78716c", dark: "#44403c", light: "#d6d3d1" }
  ];

  const DEFAULT_POEM = [
    {
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
    },
    {
      title: "The Road Not Taken",
      author: "Robert Frost",
      stanzas: [
        [
          "Two roads diverged in a yellow wood,",
          "And sorry I could not travel both",
          "And be one traveler, long I stood."
        ],
        [
          "And looked down one as far as I could",
          "To where it bent in the undergrowth;",
          "Then took the other, as just as fair."
        ],
        [
          "And having perhaps the better claim,",
          "Because it was grassy and wanted wear;",
          "Though as for that the passing there."
        ],
        [
          "Had worn them really about the same,",
          "And both that morning equally lay",
          "In leaves no step had trodden black."
        ],
        [
          "Oh, I kept the first for another day!",
          "Yet knowing how way leads on to way,",
          "I doubted if I should ever come back."
        ],
        [
          "I shall be telling this with a sigh",
          "Somewhere ages and ages hence:",
          "Two roads diverged in a wood, and I—",
          "I took the one less traveled by,",
          "And that has made all the difference."
        ]
      ]
    }
  ];

  // =========================================================================
  // Physics Primitives (Verlet Particles & Constraints)
  // =========================================================================

  class Particle {
    constructor(x, y, char = "•", pinned = false) {
      this.x = x;
      this.y = y;
      this.ox = x;
      this.oy = y;
      this.pinned = pinned;
      this.char = char;
      this.radius = 5.2;
      this.isBlock = false;
      this.blockData = null; // { lines: [], width, height }
      this.lastSoundTime = 0;
    }
  }

  class CurtainBead {
    constructor(x, y, shape, palette, shine, radius = 5.0, pinned = false) {
      this.x = x;
      this.y = y;
      this.ox = x;
      this.oy = y;
      this.pinned = pinned;
      this.shape = shape;       // 'sphere' | 'star' | 'triangle' | 'hexagon' | 'octagon' | 'rhombus'
      this.palette = palette;   // { main, dark, light }
      this.shine = shine;       // boolean
      this.radius = radius;
      this.lastSoundTime = 0;
    }
  }

  class Constraint {
    constructor(p1, p2, length) {
      this.p1 = p1;
      this.p2 = p2;
      this.length = length !== undefined ? length : Math.hypot(p2.x - p1.x, p2.y - p1.y);
    }

    resolve() {
      const dx = this.p2.x - this.p1.x;
      const dy = this.p2.y - this.p1.y;
      const dist = Math.hypot(dx, dy) || 0.001;
      const diff = (dist - this.length) / dist;

      if (!this.p1.pinned && !this.p2.pinned) {
        this.p1.x += dx * 0.5 * diff;
        this.p1.y += dy * 0.5 * diff;
        this.p2.x -= dx * 0.5 * diff;
        this.p2.y -= dy * 0.5 * diff;
      } else if (!this.p1.pinned) {
        this.p1.x += dx * diff;
        this.p1.y += dy * diff;
      } else if (!this.p2.pinned) {
        this.p2.x -= dx * diff;
        this.p2.y -= dy * diff;
      }
    }
  }

  // =========================================================================
  // Curtain String (Doorway Beaded Curtain Component)
  // =========================================================================

  class CurtainString {
    constructor(baseX, startY, count, linkLen = 17) {
      this.baseX = baseX;
      this.startY = startY;
      this.particles = [];
      this.constraints = [];
      this.buildString(count, linkLen);
    }

    buildString(count, linkLen) {
      let curY = this.startY;
      // Top anchor bead attached to doorway beam
      const anchor = new CurtainBead(this.baseX, curY, "sphere", BEAD_PALETTES[8], false, 3.5, true);
      this.particles.push(anchor);

      // Harmonious per-string palette pairing
      const palIdx = Math.floor(Math.random() * BEAD_PALETTES.length);
      const primaryPal = BEAD_PALETTES[palIdx];
      const accentPal = BEAD_PALETTES[(palIdx + 4) % BEAD_PALETTES.length];

      for (let i = 0; i < count; i++) {
        curY += linkLen;
        // Diverse geometric bead shape alternating down the string
        const shape = BEAD_SHAPES[(i + Math.floor(this.baseX / 42)) % BEAD_SHAPES.length];
        const pal = (i % 4 === 0) ? accentPal : primaryPal;
        const shine = (i % 2 === 0);
        let rad = 5.0;
        if (shape === "star") rad = 6.2;
        else if (shape === "rhombus") rad = 5.6;
        else if (shape === "octagon") rad = 5.2;

        const bead = new CurtainBead(this.baseX, curY, shape, pal, shine, rad);
        this.particles.push(bead);
        this.constraints.push(new Constraint(this.particles[this.particles.length - 2], bead, linkLen));
      }
    }
  }

  // =========================================================================
  // Stanza Chain Assembly (Non-Uniform, Organically Staggered)
  // =========================================================================

  class StanzaChainAssembly {
    constructor(baseX, startY, stanza1, stanza2, chainIndex, config) {
      this.baseX = baseX;
      this.startY = startY;
      this.chainIndex = chainIndex;
      this.particles = [];
      this.constraints = [];
      this.config = config;

      this.buildChain(stanza1, stanza2);
    }

    buildChain(stanza1, stanza2) {
      const linkLen = 15;
      const clearance = 24; // Generous clearance so beads never touch stanza cards
      let curY = this.startY;

      // 1. Pinned Top Anchor
      const anchor = new Particle(this.baseX, curY, "⚓", true);
      this.particles.push(anchor);

      // 2. Organically Staggered Top Drop:
      // Each chain has an intentionally different drop length before Stanza 1
      // Creating pronounced vertical contrast between adjacent chains
      // Chain 0: 3 beads (~48px)   -> Stanza 1 sits very high (Y ~ 116px)
      // Chain 1: 15 beads (~240px) -> Stanza 1 sits deep down (Y ~ 308px, a full 192px lower than Chain 0!)
      // Chain 2: 7 beads (~112px)  -> Stanza 1 sits mid-level (Y ~ 180px, in between!)
      // Chain 3: 14 beads (~224px) -> Stanza 1 sits lower-mid
      const topDropSequence = [3, 15, 7, 14, 4, 11];
      const topCount = topDropSequence[this.chainIndex % topDropSequence.length];

      for (let i = 0; i < topCount; i++) {
        curY += linkLen;
        const char = BEAD_CHARS[Math.floor(Math.random() * BEAD_CHARS.length)];
        const p = new Particle(this.baseX, curY, char);
        this.particles.push(p);
        this.constraints.push(new Constraint(this.particles[this.particles.length - 2], p, linkLen));
      }

      // 3. Stanza 1 Block
      const s1Data = this.measureStanza(stanza1 || ["(Stanza Line 1)", "(Stanza Line 2)"]);
      const s1HalfHeight = s1Data.height / 2;
      curY += clearance + s1HalfHeight;
      const s1 = new Particle(this.baseX, curY);
      s1.isBlock = true;
      s1.blockData = s1Data;
      this.particles.push(s1);
      this.constraints.push(new Constraint(this.particles[this.particles.length - 2], s1, clearance + s1HalfHeight));

      // 4. Organically Staggered Bridge Chain between Stanza 1 and Stanza 2
      // Different vertical link count for each chain
      curY += s1HalfHeight + clearance;
      // Staggered Bridge Chain between Stanza 1 and Stanza 2:
      // Chain 0: 6 beads (~96px)   -> Stanza 2 sits around Y ~ 330px
      // Chain 1: 14 beads (~224px) -> Stanza 2 sits down around Y ~ 640px!
      // Chain 2: 8 beads (~128px)  -> Stanza 2 sits around Y ~ 430px
      const midDropSequence = [6, 14, 8, 13, 7, 12];
      const midCount = midDropSequence[this.chainIndex % midDropSequence.length];

      for (let i = 0; i < midCount; i++) {
        const char = BEAD_CHARS[Math.floor(Math.random() * BEAD_CHARS.length)];
        const p = new Particle(this.baseX, curY, char);
        this.particles.push(p);
        if (i === 0) {
          this.constraints.push(new Constraint(s1, p, s1HalfHeight + clearance));
        } else {
          this.constraints.push(new Constraint(this.particles[this.particles.length - 2], p, linkLen));
        }
        curY += linkLen;
      }

      // 5. Stanza 2 Block
      const s2Data = this.measureStanza(stanza2 || ["(Stanza Line 3)", "(Stanza Line 4)"]);
      const s2HalfHeight = s2Data.height / 2;
      curY += clearance + s2HalfHeight;
      const s2 = new Particle(this.baseX, curY);
      s2.isBlock = true;
      s2.blockData = s2Data;
      this.particles.push(s2);
      this.constraints.push(new Constraint(this.particles[this.particles.length - 2], s2, clearance + s2HalfHeight));

      // 6. Trailing tail beads (varying fringe)
      curY += s2HalfHeight + clearance;
      const tailDropSequence = [6, 11, 5, 9, 7, 10];
      const tailCount = tailDropSequence[this.chainIndex % tailDropSequence.length];

      for (let i = 0; i < tailCount; i++) {
        const char = BEAD_CHARS[Math.floor(Math.random() * BEAD_CHARS.length)];
        const p = new Particle(this.baseX, curY, char);
        this.particles.push(p);
        if (i === 0) {
          this.constraints.push(new Constraint(s2, p, s2HalfHeight + clearance));
        } else {
          this.constraints.push(new Constraint(this.particles[this.particles.length - 2], p, linkLen));
        }
        curY += linkLen;
      }
    }

    measureStanza(lines) {
      const lineList = Array.isArray(lines) ? lines : [String(lines)];
      let maxLen = 0;
      lineList.forEach(l => { if (l.length > maxLen) maxLen = l.length; });
      // Arvo slab serif is slightly wider and taller with generous breathing room
      const width = Math.max(200, Math.min(380, maxLen * 9.2 + 48));
      const height = lineList.length * 26 + 34;
      return { lines: lineList, width, height };
    }
  }

  // =========================================================================
  // Main Physics Engine (Curtain & Stanza Assemblies)
  // =========================================================================

  class PoemChimesEngine {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.curtainStrings = [];
      this.stanzaChains = [];
      this.draggedParticle = null;
      this.mouse = { x: 0, y: 0, down: false, px: 0, py: 0 };
      this.time = 0;

      this.config = {
        gravity: 0.24,
        damping: 0.984, // High silky damping, matching original Chimes
        swaySpeed: 0.02,
        swayIntensity: 0.012,
        curtainSpacing: 28, // Spacing between curtain strings
        stanzaSpacing: 380, // Spacing between poem stanza chains
        chainSpacingY: 42
      };

      this.activePoemIndex = 0;
      this.activePoem = DEFAULT_POEM[0];
      this.initEvents();
      this.resize();
      this.loop = this.loop.bind(this);
      requestAnimationFrame(this.loop);
    }

    cyclePoemPreset() {
      this.activePoemIndex = (this.activePoemIndex + 1) % DEFAULT_POEM.length;
      this.activePoem = DEFAULT_POEM[this.activePoemIndex];
      this.buildAssemblies();
    }

    loadCustomPoem(stanzas) {
      if (Array.isArray(stanzas) && stanzas.length > 0) {
        this.activePoem = {
          title: "Custom Reflection",
          author: "User",
          stanzas: stanzas
        };
        this.buildAssemblies();
      }
    }

    setPoem(poemData) {
      if (poemData && Array.isArray(poemData.stanzas)) {
        this.activePoem = poemData;
        this.buildAssemblies();
      }
    }

    resize() {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      this.width = rect.width;
      this.height = Math.max(880, window.innerHeight * 0.96);
      this.canvas.width = this.width * dpr;
      this.canvas.height = this.height * dpr;
      this.canvas.style.width = `${this.width}px`;
      this.canvas.style.height = `${this.height}px`;
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.buildAssemblies();
    }

    buildAssemblies() {
      this.curtainStrings = [];
      this.stanzaChains = [];

      const startY = this.config.chainSpacingY;

      // 1. Build Stanza Chains (Centered horizontally)
      const stanzas = this.activePoem.stanzas || [];
      const numStanzaChains = Math.max(1, Math.ceil(stanzas.length / 2));
      const totalStanzaWidth = (numStanzaChains - 1) * this.config.stanzaSpacing;
      const stanzaStartX = (this.width - totalStanzaWidth) / 2;

      const stanzaXs = [];
      for (let i = 0; i < numStanzaChains; i++) {
        const x = stanzaStartX + i * this.config.stanzaSpacing;
        stanzaXs.push(x);
        const s1 = stanzas[i * 2] || null;
        const s2 = stanzas[i * 2 + 1] || null;
        const chain = new StanzaChainAssembly(x, startY, s1, s2, i, this.config);
        this.stanzaChains.push(chain);
      }

      // 2. Build Beaded Doorway Curtain Strings (spanning across entire width)
      const spacing = this.config.curtainSpacing;
      const margin = 36;
      const numStrings = Math.floor((this.width - margin * 2) / spacing);

      for (let i = 0; i <= numStrings; i++) {
        const x = margin + i * spacing;

        // Skip string if it overlaps directly on the exact central drop of a stanza chain anchor
        const isNearStanzaAnchor = stanzaXs.some(sx => Math.abs(x - sx) < 14);
        if (isNearStanzaAnchor) continue;

        // Organic arched curtain fringe length (24 to 34 beads per string)
        const archWave = Math.sin((i / numStrings) * Math.PI) * 4;
        const count = Math.max(22, Math.min(34, Math.floor(25 + archWave + (Math.sin(i * 1.5) * 2))));

        const cs = new CurtainString(x, startY, count, 17);
        this.curtainStrings.push(cs);
      }
    }

    initEvents() {
      window.addEventListener("resize", () => this.resize());

      const getPos = (e) => {
        const r = this.canvas.getBoundingClientRect();
        return {
          x: (e.clientX || (e.touches && e.touches[0].clientX)) - r.left,
          y: (e.clientY || (e.touches && e.touches[0].clientY)) - r.top
        };
      };

      const onDown = (e) => {
        const pos = getPos(e);
        this.mouse.x = pos.x;
        this.mouse.y = pos.y;
        this.mouse.px = pos.x;
        this.mouse.py = pos.y;
        this.mouse.down = true;

        // "dragging is for only for chains with stanzas"
        // Search strictly among stanzaChains for the closest particle or block
        let closest = null;
        let minDist = 48;

        this.stanzaChains.forEach(chain => {
          chain.particles.forEach(p => {
            if (p.pinned) return;
            const hitRadius = p.isBlock
              ? Math.max(p.blockData.width, p.blockData.height) / 2 + 12
              : p.radius * 2.8;
            const dist = Math.hypot(p.x - pos.x, p.y - pos.y);
            if (dist < hitRadius && dist < minDist) {
              minDist = dist;
              closest = p;
            }
          });
        });

        if (closest) {
          this.draggedParticle = closest;
          if (window.DhritiAudio) {
            window.DhritiAudio.playChime(Math.floor((pos.x / this.width) * 16), 0.65);
          }
        }
      };

      const onMove = (e) => {
        const pos = getPos(e);
        const dx = pos.x - this.mouse.x;
        const dy = pos.y - this.mouse.y;

        this.mouse.px = this.mouse.x;
        this.mouse.py = this.mouse.y;
        this.mouse.x = pos.x;
        this.mouse.y = pos.y;

        if (this.draggedParticle) {
          // Direct drag manipulation for stanza cards/beads
          this.draggedParticle.x = pos.x;
          this.draggedParticle.y = pos.y;
        } else {
          // Hovering across doorway curtain strings:
          // Moves like the authentic doorway beaded curtain as cursor passes across them
          const mouseSpeed = Math.hypot(dx, dy);
          if (mouseSpeed > 0.4) {
            const sweepRadius = 32;
            const now = performance.now();

            // 1. Hover through curtain strings
            this.curtainStrings.forEach((cs) => {
              if (Math.abs(cs.baseX - pos.x) > sweepRadius + 18) return;

              cs.particles.forEach((p) => {
                if (p.pinned) return;
                const dist = Math.hypot(p.x - pos.x, p.y - pos.y);
                if (dist < sweepRadius) {
                  const proximity = 1 - dist / sweepRadius;
                  const pushDir = Math.abs(dx) > 0.3 ? Math.sign(dx) : (p.x >= pos.x ? 1 : -1);
                  // Smooth, bounded impulse (avoids erratic jerkiness)
                  const impulse = pushDir * Math.min(4.8, (Math.abs(dx) * 0.22 + 1.2) * proximity);

                  // Smooth Verlet impulse: adjust ox so velocity increases naturally
                  p.ox -= impulse * 0.55;
                  p.x += impulse * 0.45;

                  // Play chime if moving noticeably, throttled
                  if (Math.abs(impulse) > 0.8 && (!p.lastSoundTime || now - p.lastSoundTime > 160)) {
                    p.lastSoundTime = now;
                    if (window.DhritiAudio) {
                      const noteIdx = Math.floor((p.x / this.width) * 17);
                      window.DhritiAudio.playChime(noteIdx, Math.min(0.6, Math.abs(impulse) / 4.8));
                    }
                  }
                }
              });
            });

            // 2. Also gently sway stanza letter beads on hover if cursor brushes past
            this.stanzaChains.forEach((chain) => {
              if (Math.abs(chain.baseX - pos.x) > sweepRadius + 50) return;

              chain.particles.forEach((p) => {
                if (p.pinned || p.isBlock) return;
                const dist = Math.hypot(p.x - pos.x, p.y - pos.y);
                if (dist < sweepRadius) {
                  const proximity = 1 - dist / sweepRadius;
                  const pushDir = Math.abs(dx) > 0.3 ? Math.sign(dx) : (p.x >= pos.x ? 1 : -1);
                  const impulse = pushDir * Math.min(3.8, (Math.abs(dx) * 0.18 + 0.8) * proximity);
                  p.ox -= impulse * 0.5;
                  p.x += impulse * 0.5;
                }
              });
            });
          }
        }
      };

      const onUp = () => {
        this.mouse.down = false;
        this.draggedParticle = null;
      };

      this.canvas.addEventListener("mousedown", onDown);
      this.canvas.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);

      this.canvas.addEventListener("touchstart", onDown, { passive: true });
      this.canvas.addEventListener("touchmove", onMove, { passive: true });
      window.addEventListener("touchend", onUp);
    }

    step() {
      this.time += 1;
      const swayTime = this.time * this.config.swaySpeed;

      // 1. Update Curtain Strings
      this.curtainStrings.forEach((cs, csIdx) => {
        const stringPhase = csIdx * 0.26;
        const breeze = Math.sin(swayTime + stringPhase) * (this.config.swayIntensity * 0.85);

        cs.particles.forEach((p) => {
          if (p.pinned) return;

          const vx = (p.x - p.ox) * this.config.damping;
          const vy = (p.y - p.oy) * this.config.damping;

          p.ox = p.x;
          p.oy = p.y;

          // Plumb-line restoring force centered exactly on string's baseX
          const plumb = (cs.baseX - p.x) * 0.0038;

          p.x += vx + breeze + plumb;
          p.y += vy + this.config.gravity * 0.88;
        });

        // Constraint relaxation iterations
        for (let iter = 0; iter < 3; iter++) {
          cs.constraints.forEach(c => c.resolve());
        }
      });

      // 2. Update Stanza Chains
      this.stanzaChains.forEach((chain, cIdx) => {
        const chainPhase = cIdx * 1.2;
        const ambientWind = Math.sin(swayTime + chainPhase) * this.config.swayIntensity;

        chain.particles.forEach((p, pIdx) => {
          if (p.pinned) return;
          if (p === this.draggedParticle) return;

          const vx = (p.x - p.ox) * this.config.damping;
          const vy = (p.y - p.oy) * this.config.damping;

          p.ox = p.x;
          p.oy = p.y;

          const wind = ambientWind * (1 + (pIdx / chain.particles.length) * 0.35);
          const plumbRestoring = (chain.baseX - p.x) * 0.0035;

          p.x += vx + wind + plumbRestoring;
          p.y += vy + (p.isBlock ? this.config.gravity * 1.15 : this.config.gravity);
        });

        for (let iter = 0; iter < 4; iter++) {
          chain.constraints.forEach(c => c.resolve());
        }
      });
    }

    draw() {
      const ctx = this.ctx;
      ctx.clearRect(0, 0, this.width, this.height);

      const startY = this.config.chainSpacingY;

      // 1. Draw Architectural Doorway Header Beam
      this.drawDoorwayBeam(ctx, startY);

      // 2. Draw Curtain Strings (Background Layer)
      this.curtainStrings.forEach((cs) => {
        // String thread
        ctx.strokeStyle = "rgba(203, 213, 225, 0.22)";
        ctx.lineWidth = 1.0;

        ctx.beginPath();
        ctx.moveTo(cs.particles[0].x, cs.particles[0].y);
        for (let i = 1; i < cs.particles.length; i++) {
          ctx.lineTo(cs.particles[i].x, cs.particles[i].y);
        }
        ctx.stroke();

        // Geometric beads
        for (let i = 1; i < cs.particles.length; i++) {
          this.drawGeometricBead(ctx, cs.particles[i]);
        }
      });

      // 3. Draw Stanza Chains (Foreground Layer)
      this.stanzaChains.forEach((chain) => {
        // Draw string segments between adjacent particles (terminating at block eyelets)
        ctx.strokeStyle = "rgba(226, 232, 240, 0.42)";
        ctx.lineWidth = 1.8;

        for (let i = 0; i < chain.particles.length - 1; i++) {
          const p1 = chain.particles[i];
          const p2 = chain.particles[i + 1];

          let startX = p1.x;
          let startYPos = p1.y;
          let endX = p2.x;
          let endYPos = p2.y;

          if (p1.isBlock && p1.blockData) {
            startYPos += p1.blockData.height / 2;
          }
          if (p2.isBlock && p2.blockData) {
            endYPos -= p2.blockData.height / 2;
          }

          ctx.beginPath();
          ctx.moveTo(startX, startYPos);
          ctx.lineTo(endX, endYPos);
          ctx.stroke();
        }

        // Draw stanzas with frosted parchment background
        chain.particles.forEach((p) => {
          if (p.isBlock) {
            this.drawStanzaBlock(ctx, p, chain);
          }
        });

        // Draw letter beads
        chain.particles.forEach((p, i) => {
          if (!p.isBlock) {
            this.drawLetterBead(ctx, p, i === 0);
          }
        });
      });
    }

    drawDoorwayBeam(ctx, startY) {
      const beamY = startY - 14;
      const margin = 24;
      const beamWidth = this.width - margin * 2;

      ctx.save();
      // Beam shadow
      ctx.shadowColor = "rgba(0, 0, 0, 0.55)";
      ctx.shadowBlur = 12;
      ctx.shadowOffsetY = 4;

      // Wooden / bronze beveled beam
      const beamGrad = ctx.createLinearGradient(0, beamY, 0, beamY + 12);
      beamGrad.addColorStop(0, "#475569");
      beamGrad.addColorStop(0.3, "#334155");
      beamGrad.addColorStop(0.7, "#1e293b");
      beamGrad.addColorStop(1, "#0f172a");

      ctx.fillStyle = beamGrad;
      ctx.beginPath();
      ctx.roundRect(margin, beamY, beamWidth, 10, 4);
      ctx.fill();

      // Top specular highlight line
      ctx.strokeStyle = "rgba(255, 255, 255, 0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(margin + 4, beamY + 1);
      ctx.lineTo(margin + beamWidth - 4, beamY + 1);
      ctx.stroke();

      // Brass mounting finials on ends
      ctx.fillStyle = "#f59e0b";
      ctx.beginPath();
      ctx.arc(margin, beamY + 5, 6, 0, Math.PI * 2);
      ctx.arc(margin + beamWidth, beamY + 5, 6, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    }

    drawGeometricBead(ctx, bead) {
      const x = bead.x;
      const y = bead.y;
      const r = bead.radius;
      const shape = bead.shape;
      const pal = bead.palette;
      const shine = bead.shine;

      ctx.save();
      ctx.shadowColor = "rgba(0, 0, 0, 0.3)";
      ctx.shadowBlur = 3;
      ctx.shadowOffsetY = 1.5;

      switch (shape) {
        case "sphere":
          this.drawSphere(ctx, x, y, r, pal, shine);
          break;
        case "star":
          this.drawStar(ctx, x, y, 5, r, r * 0.48, pal, shine);
          break;
        case "triangle":
          this.drawTriangle(ctx, x, y, r, true, pal, shine);
          break;
        case "hexagon":
          this.drawPolygon(ctx, x, y, r, 6, pal, shine);
          break;
        case "octagon":
          this.drawPolygon(ctx, x, y, r, 8, pal, shine);
          break;
        case "rhombus":
        default:
          this.drawRhombus(ctx, x, y, r * 0.85, r * 1.3, pal, shine);
          break;
      }
      ctx.restore();
    }

    drawSphere(ctx, x, y, r, pal, shine) {
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      if (shine) {
        const grad = ctx.createRadialGradient(x - r * 0.35, y - r * 0.35, r * 0.12, x, y, r);
        grad.addColorStop(0, "#ffffff");
        grad.addColorStop(0.35, pal.light);
        grad.addColorStop(0.75, pal.main);
        grad.addColorStop(1, pal.dark);
        ctx.fillStyle = grad;
      } else {
        ctx.fillStyle = pal.main;
      }
      ctx.fill();
    }

    drawStar(ctx, x, y, spikes, outerRadius, innerRadius, pal, shine) {
      let rot = (Math.PI / 2) * 3;
      const step = Math.PI / spikes;
      ctx.beginPath();
      ctx.moveTo(x, y - outerRadius);
      for (let i = 0; i < spikes; i++) {
        ctx.lineTo(x + Math.cos(rot) * outerRadius, y + Math.sin(rot) * outerRadius);
        rot += step;
        ctx.lineTo(x + Math.cos(rot) * innerRadius, y + Math.sin(rot) * innerRadius);
        rot += step;
      }
      ctx.closePath();
      if (shine) {
        const grad = ctx.createRadialGradient(x, y - outerRadius * 0.3, outerRadius * 0.1, x, y, outerRadius);
        grad.addColorStop(0, "#ffffff");
        grad.addColorStop(0.4, pal.light);
        grad.addColorStop(1, pal.dark);
        ctx.fillStyle = grad;
      } else {
        ctx.fillStyle = pal.main;
      }
      ctx.fill();
    }

    drawTriangle(ctx, x, y, r, pointingUp, pal, shine) {
      const h = (r * Math.sqrt(3)) / 2;
      ctx.beginPath();
      if (pointingUp) {
        ctx.moveTo(x, y - r);
        ctx.lineTo(x + r, y + h);
        ctx.lineTo(x - r, y + h);
      } else {
        ctx.moveTo(x, y + r);
        ctx.lineTo(x + r, y - h);
        ctx.lineTo(x - r, y - h);
      }
      ctx.closePath();
      if (shine) {
        const grad = ctx.createLinearGradient(x - r, y - r, x + r, y + r);
        grad.addColorStop(0, pal.light);
        grad.addColorStop(0.6, pal.main);
        grad.addColorStop(1, pal.dark);
        ctx.fillStyle = grad;
      } else {
        ctx.fillStyle = pal.main;
      }
      ctx.fill();
    }

    drawPolygon(ctx, x, y, r, sides, pal, shine) {
      ctx.beginPath();
      for (let i = 0; i < sides; i++) {
        const a = (i * 2 * Math.PI) / sides - Math.PI / 2;
        const px = x + r * Math.cos(a);
        const py = y + r * Math.sin(a);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      if (shine) {
        const grad = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, r * 0.1, x, y, r);
        grad.addColorStop(0, "#ffffff");
        grad.addColorStop(0.3, pal.light);
        grad.addColorStop(0.7, pal.main);
        grad.addColorStop(1, pal.dark);
        ctx.fillStyle = grad;
      } else {
        ctx.fillStyle = pal.main;
      }
      ctx.fill();
    }

    drawRhombus(ctx, x, y, rw, rh, pal, shine) {
      ctx.beginPath();
      ctx.moveTo(x, y - rh);
      ctx.lineTo(x + rw, y);
      ctx.lineTo(x, y + rh);
      ctx.lineTo(x - rw, y);
      ctx.closePath();
      if (shine) {
        const grad = ctx.createLinearGradient(x - rw, y - rh, x + rw, y + rh);
        grad.addColorStop(0, pal.light);
        grad.addColorStop(0.5, pal.main);
        grad.addColorStop(1, pal.dark);
        ctx.fillStyle = grad;
      } else {
        ctx.fillStyle = pal.main;
      }
      ctx.fill();
    }

    drawLetterBead(ctx, p, isAnchor) {
      if (isAnchor) {
        ctx.fillStyle = "rgba(255, 255, 255, 0.45)";
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
        ctx.fill();
        return;
      }

      const r = p.radius || 5.2;

      // Metallic bead sphere with stamped letter
      const grad = ctx.createRadialGradient(p.x - 1.5, p.y - 1.5, 0.8, p.x, p.y, r);
      grad.addColorStop(0, "rgba(255, 255, 255, 0.96)");
      grad.addColorStop(0.55, "rgba(203, 213, 225, 0.90)");
      grad.addColorStop(1, "rgba(71, 85, 105, 0.82)");

      ctx.save();
      ctx.shadowColor = "rgba(0, 0, 0, 0.38)";
      ctx.shadowBlur = 4;
      ctx.shadowOffsetY = 2;

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      ctx.fillStyle = "#0f172a";
      ctx.font = "bold 6.5px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(p.char, p.x, p.y + 0.3);
    }

    drawStanzaBlock(ctx, p, chain) {
      const data = p.blockData;
      if (!data) return;

      // Estimate local tilt angle from neighboring chain particles
      const pIdx = chain.particles.indexOf(p);
      const prev = chain.particles[pIdx - 1];
      const next = chain.particles[pIdx + 1];

      let angle = 0;
      if (prev && next) {
        angle = Math.atan2(next.x - prev.x, next.y - prev.y) * 0.38;
      }

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(-angle);

      const hw = data.width / 2;
      const hh = data.height / 2;

      // Stanza Card Body: Frosted translucent parchment card
      ctx.shadowColor = "rgba(0, 0, 0, 0.45)";
      ctx.shadowBlur = 18;
      ctx.shadowOffsetY = 8;

      ctx.fillStyle = "rgba(255, 255, 255, 0.95)";
      ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
      ctx.lineWidth = 1.4;

      ctx.beginPath();
      ctx.roundRect(-hw, -hh, data.width, data.height, 14);
      ctx.fill();
      ctx.stroke();

      ctx.restore(); // remove card shadow for crisp text rendering

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(-angle);

      // Render Stanza Lines using Arvo slab serif
      ctx.fillStyle = "#0f172a";
      ctx.font = "italic 15px 'Arvo', 'Georgia', serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      const startY = -hh + 25;
      data.lines.forEach((line, idx) => {
        ctx.fillText(line, 0, startY + idx * 26);
      });

      // Subtle suspension loop rings at top and bottom
      ctx.fillStyle = "#475569";
      ctx.beginPath();
      ctx.arc(0, -hh + 4, 3, 0, Math.PI * 2);
      ctx.arc(0, hh - 4, 3, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    }

    loop() {
      this.step();
      this.draw();
      requestAnimationFrame(this.loop);
    }
  }

  let activeEngineInstance = null;

  window.DhritiPoemChimes = window.DhritiChimes = {
    init: (canvasOrId) => {
      const canvas = typeof canvasOrId === "string" ? document.getElementById(canvasOrId) : canvasOrId;
      if (canvas) {
        activeEngineInstance = new PoemChimesEngine(canvas);
        return activeEngineInstance;
      }
      return null;
    },
    nextPoemPreset: () => {
      if (activeEngineInstance) {
        activeEngineInstance.cyclePoemPreset();
      }
    },
    loadCustomPoem: (stanzas) => {
      if (activeEngineInstance) {
        activeEngineInstance.loadCustomPoem(stanzas);
      }
    },
    getInstance: () => activeEngineInstance,
    DEFAULT_POEM
  };
})();
