/**
 * Dhriti Chimes Physics & Interactive Poem Installation
 * Inspired by Niyam Vora's Chimes (niyamvora.github.io/chimes).
 *
 * Implements Verlet physics, harmonic ambient sway, direct drag-and-drop
 * manipulation, suspended stanza blocks, and procedural chime acoustics.
 */
(() => {
  "use strict";

  const BEAD_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789✦◊◈⚓⏣§¶";

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
    }
  ];

  class Particle {
    constructor(x, y, char = "•", pinned = false) {
      this.x = x;
      this.y = y;
      this.ox = x;
      this.oy = y;
      this.pinned = pinned;
      this.char = char;
      this.radius = 5.0; // Refined, delicate bead radius
      this.isBlock = false;
      this.blockData = null; // { lines: [], width, height }
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

  class ChainAssembly {
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
      const linkLen = 14;
      const clearance = 20; // Clear spacing above and below stanza blocks so beads never overlap
      let curY = this.startY;

      // 1. Pinned Top Anchor
      const anchor = new Particle(this.baseX, curY, "⚓", true);
      this.particles.push(anchor);

      // 2. Upper chain beads (5 to 7 beads)
      const topCount = 5 + Math.floor(Math.random() * 3);
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
      // Position particle at its center: clearance + halfHeight below the last bead
      curY += clearance + s1HalfHeight;
      const s1 = new Particle(this.baseX, curY);
      s1.isBlock = true;
      s1.blockData = s1Data;
      this.particles.push(s1);
      // Constraint length matches the center offset exactly
      this.constraints.push(new Constraint(this.particles[this.particles.length - 2], s1, clearance + s1HalfHeight));

      // 4. Middle chain connecting Stanza 1 to Stanza 2 (6 to 8 beads)
      curY += s1HalfHeight + clearance;
      const midCount = 6 + Math.floor(Math.random() * 3);
      for (let i = 0; i < midCount; i++) {
        const char = BEAD_CHARS[Math.floor(Math.random() * BEAD_CHARS.length)];
        const p = new Particle(this.baseX, curY, char);
        this.particles.push(p);
        if (i === 0) {
          // Constraint from s1 center to first middle bead
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

      // 6. Trailing tail beads (4 to 6 beads)
      curY += s2HalfHeight + clearance;
      const tailCount = 4 + Math.floor(Math.random() * 3);
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
      const width = Math.max(180, Math.min(340, maxLen * 8.5 + 36));
      const height = lineList.length * 20 + 26;
      return { lines: lineList, width, height };
    }
  }

  class PoemChimesEngine {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.chains = [];
      this.draggedParticle = null;
      this.mouse = { x: 0, y: 0, down: false, px: 0, py: 0 };
      this.time = 0;

      this.config = {
        gravity: 0.28,
        damping: 0.982,
        swaySpeed: 0.022,
        swayIntensity: 0.012,
        spacing: 340,
        chainSpacingY: 40
      };

      this.activePoemIndex = 0;
      this.activePoem = DEFAULT_POEM[0];
      this.initEvents();
      this.resize();
      this.buildAssemblies();
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
      this.height = Math.max(850, window.innerHeight * 0.95);
      this.canvas.width = this.width * dpr;
      this.canvas.height = this.height * dpr;
      this.canvas.style.width = `${this.width}px`;
      this.canvas.style.height = `${this.height}px`;
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.buildAssemblies();
    }

    buildAssemblies() {
      this.chains = [];
      const stanzas = this.activePoem.stanzas || [];
      const numChains = Math.max(1, Math.ceil(stanzas.length / 2));

      // Calculate total width to center the chains perfectly
      const totalWidth = (numChains - 1) * this.config.spacing;
      const startX = (this.width - totalWidth) / 2;

      for (let i = 0; i < numChains; i++) {
        const x = startX + i * this.config.spacing;
        const s1 = stanzas[i * 2] || null;
        const s2 = stanzas[i * 2 + 1] || null;
        const chain = new ChainAssembly(x, this.config.chainSpacingY, s1, s2, i, this.config);
        this.chains.push(chain);
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

        // Find nearest particle or block within click distance
        let closest = null;
        let minDist = 36;

        this.chains.forEach(chain => {
          chain.particles.forEach(p => {
            if (p.pinned) return;
            const hitRadius = p.isBlock
              ? Math.max(p.blockData.width, p.blockData.height) / 2
              : p.radius * 2;
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
            window.DhritiAudio.playChime(Math.floor(pos.x / 80), 0.6);
          }
        }
      };

      const onMove = (e) => {
        const pos = getPos(e);
        this.mouse.px = this.mouse.x;
        this.mouse.py = this.mouse.y;
        this.mouse.x = pos.x;
        this.mouse.y = pos.y;

        if (this.draggedParticle) {
          this.draggedParticle.x = pos.x;
          this.draggedParticle.y = pos.y;
        } else if (this.mouse.down) {
          // Swipe across strings effect (Chimes interaction)
          this.chains.forEach((chain, cIdx) => {
            chain.particles.forEach((p, pIdx) => {
              if (p.pinned) return;
              const d = Math.hypot(p.x - pos.x, p.y - pos.y);
              if (d < 24) {
                const push = (pos.x - this.mouse.px) * 0.4;
                p.x += push;
                if (Math.abs(push) > 1.2 && window.DhritiAudio) {
                  window.DhritiAudio.playChime(cIdx * 3 + (pIdx % 4), Math.min(1, Math.abs(push) / 5));
                }
              }
            });
          });
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

      this.chains.forEach((chain, cIdx) => {
        // Natural balanced breeze wave across chains
        const chainPhase = cIdx * 1.2;
        const ambientWind = Math.sin(swayTime + chainPhase) * this.config.swayIntensity;

        chain.particles.forEach((p, pIdx) => {
          if (p.pinned) return;
          if (p === this.draggedParticle) return;

          const vx = (p.x - p.ox) * this.config.damping;
          const vy = (p.y - p.oy) * this.config.damping;

          p.ox = p.x;
          p.oy = p.y;

          // Depth-dependent wind force
          const wind = ambientWind * (1 + (pIdx / chain.particles.length) * 0.4);

          // Plumb-line restoring force centered exactly on chain anchor baseX
          // Prevents one-sided drifting or leaning to the right
          const plumbRestoring = (chain.baseX - p.x) * 0.0035;

          p.x += vx + wind + plumbRestoring;
          p.y += vy + this.config.gravity;
        });

        // Resolve distance constraints
        for (let iter = 0; iter < 4; iter++) {
          chain.constraints.forEach(c => c.resolve());
        }
      });
    }

    draw() {
      const ctx = this.ctx;
      ctx.clearRect(0, 0, this.width, this.height);

      this.chains.forEach((chain, cIdx) => {
        // Draw string segments between adjacent particles (terminating at block eyelets)
        ctx.strokeStyle = "rgba(226, 232, 240, 0.35)";
        ctx.lineWidth = 1.6;

        for (let i = 0; i < chain.particles.length - 1; i++) {
          const p1 = chain.particles[i];
          const p2 = chain.particles[i + 1];

          let startX = p1.x;
          let startY = p1.y;
          let endX = p2.x;
          let endY = p2.y;

          if (p1.isBlock && p1.blockData) {
            startY += p1.blockData.height / 2;
          }
          if (p2.isBlock && p2.blockData) {
            endY -= p2.blockData.height / 2;
          }

          ctx.beginPath();
          ctx.moveTo(startX, startY);
          ctx.lineTo(endX, endY);
          ctx.stroke();
        }

        // Draw stanzas first (bottom layer)
        chain.particles.forEach((p) => {
          if (p.isBlock) {
            this.drawStanzaBlock(ctx, p, chain);
          }
        });

        // Draw beads second (top layer, but never overlapping stanzas due to clearance)
        chain.particles.forEach((p, i) => {
          if (!p.isBlock) {
            this.drawBead(ctx, p, i === 0);
          }
        });
      });
    }

    drawBead(ctx, p, isAnchor) {
      if (isAnchor) {
        ctx.fillStyle = "rgba(255, 255, 255, 0.4)";
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
        ctx.fill();
        return;
      }

      const r = p.radius || 5.0;

      // Metallic bead circle with letter
      const grad = ctx.createRadialGradient(p.x - 1.5, p.y - 1.5, 0.8, p.x, p.y, r);
      grad.addColorStop(0, "rgba(255, 255, 255, 0.95)");
      grad.addColorStop(0.6, "rgba(203, 213, 225, 0.88)");
      grad.addColorStop(1, "rgba(100, 116, 139, 0.78)");

      ctx.save();
      ctx.shadowColor = "rgba(0, 0, 0, 0.35)";
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

      // Estimate local tilt angle from neighboring particles
      const pIdx = chain.particles.indexOf(p);
      const prev = chain.particles[pIdx - 1];
      const next = chain.particles[pIdx + 1];

      let angle = 0;
      if (prev && next) {
        angle = Math.atan2(next.x - prev.x, next.y - prev.y) * 0.4;
      }

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(-angle);

      const hw = data.width / 2;
      const hh = data.height / 2;

      // Stanza Card Body: Frosted translucent parchment aesthetic
      ctx.shadowColor = "rgba(0, 0, 0, 0.35)";
      ctx.shadowBlur = 14;
      ctx.shadowOffsetY = 6;

      ctx.fillStyle = "rgba(255, 255, 255, 0.88)";
      ctx.strokeStyle = "rgba(255, 255, 255, 0.6)";
      ctx.lineWidth = 1.2;

      ctx.beginPath();
      ctx.roundRect(-hw, -hh, data.width, data.height, 12);
      ctx.fill();
      ctx.stroke();

      ctx.restore(); // remove card shadow for crisp text

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(-angle);

      // Render Stanza Lines
      ctx.fillStyle = "#1e293b";
      ctx.font = "italic 13px 'Georgia', serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      const startY = -hh + 20;
      data.lines.forEach((line, idx) => {
        ctx.fillText(line, 0, startY + idx * 20);
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
