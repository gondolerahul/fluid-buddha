// The Aura — Pragya's living "liquid light" being, rendered on a 2D canvas
// (no WebGL, so Design Level 1 never pays the Three.js cost). One renderer,
// reused at every scale: the Level 1 launcher orb + avatar, and the Level 3
// summon orb. Level 2 has its own volumetric smoke field; this is the compact,
// crisp sibling that carries the SAME state-of-light language so Pragya reads as
// one continuous presence across all three designs.
//
// The form is a cluster of soft light lobes orbiting a bright core, drawn with
// additive ("lighter") blending so overlaps bloom into molten light. A slow
// breath modulates the whole body; live `energy` (mic / TTS amplitude) widens
// the orbit and brightens the core in sync with speech. State only changes the
// *behaviour* of the light — colour, cadence, symmetry — never adds chrome.

export type AuraState = 'dormant' | 'listening' | 'thinking' | 'speaking';

export interface AuraOptions {
  accent?: string;
  /** Honour prefers-reduced-motion: render one calm static frame, no loop. */
  reducedMotion?: boolean;
}

type RGB = [number, number, number];

function hexToRgb(hex: string): RGB {
  const m = /^#?([0-9a-f]{6})$/i.exec((hex || '').trim());
  if (!m) return [201, 162, 74];
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
const mix = (a: RGB, b: RGB, t: number): RGB => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];

// Cool counter-light (the "listening"/user tint) — moonstone silver.
const SILVER: RGB = [196, 204, 218];

interface Lobe { ang: number; spd: number; rad: number; size: number; phase: number; }

export class AuraCanvas {
  private ctx: CanvasRenderingContext2D | null;
  private dpr = 1;
  private w = 0;
  private h = 0;
  private raf = 0;
  private running = false;
  private reduced: boolean;

  private accent: RGB;
  private bright: RGB;       // champagne highlight (core)
  private deep: RGB;         // deep amber (outer falloff)
  private color: RGB;        // current body tint (eased)
  private target: RGB;       // state target tint
  private lobes: Lobe[] = [];

  private state: AuraState = 'dormant';
  private energy = 0;
  private energyTarget = 0;
  private energyProvider?: () => number;
  private t = 0;
  private last = 0;

  constructor(private readonly canvas: HTMLCanvasElement, opts: AuraOptions = {}) {
    this.ctx = (() => { try { return canvas.getContext('2d'); } catch { return null; } })();
    this.reduced = !!opts.reducedMotion;
    this.accent = hexToRgb(opts.accent ?? '#c9a24a');
    this.bright = mix(this.accent, [255, 248, 226], 0.62);
    this.deep = mix(this.accent, [0, 0, 0], 0.55);
    this.color = this.accent.slice() as RGB;
    this.target = this.accent.slice() as RGB;

    // Seven lobes on staggered orbits — an organic, never-repeating swirl.
    for (let i = 0; i < 7; i++) {
      this.lobes.push({
        ang: (i / 7) * Math.PI * 2,
        spd: 0.18 + (i % 3) * 0.07,
        rad: 0.16 + (i % 4) * 0.05,
        size: 0.5 + (i % 3) * 0.16,
        phase: i * 1.7,
      });
    }
    this.resize();
  }

  setAccent(hex: string): void {
    this.accent = hexToRgb(hex);
    this.bright = mix(this.accent, [255, 248, 226], 0.62);
    this.deep = mix(this.accent, [0, 0, 0], 0.55);
    if (this.state !== 'listening') this.target = this.tintFor(this.state);
  }

  setState(s: AuraState): void {
    this.state = s;
    this.target = this.tintFor(s);
    if (this.reduced) this.renderStatic();
  }

  /** Live 0..1 amplitude (mic when listening, TTS when speaking). */
  setEnergy(v: number): void { this.energyTarget = Math.max(0, Math.min(1, v)); }
  setEnergyProvider(fn: () => number): void { this.energyProvider = fn; }

  private tintFor(s: AuraState): RGB {
    if (s === 'listening') return SILVER;
    if (s === 'thinking') return mix(this.accent, [255, 244, 221], 0.3);
    if (s === 'speaking') return this.bright;
    return this.accent; // dormant
  }

  resize(): void {
    const cssW = this.canvas.clientWidth || this.canvas.width || 64;
    const cssH = this.canvas.clientHeight || this.canvas.height || 64;
    this.dpr = Math.min((typeof window !== 'undefined' && window.devicePixelRatio) || 1, 2);
    this.w = cssW; this.h = cssH;
    this.canvas.width = Math.max(1, Math.round(cssW * this.dpr));
    this.canvas.height = Math.max(1, Math.round(cssH * this.dpr));
    if (this.reduced) this.renderStatic();
  }

  start(): void {
    if (!this.ctx) return;
    if (this.reduced) { this.renderStatic(); return; }
    if (this.running) return;
    this.running = true;
    this.last = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    const loop = () => {
      if (!this.running) return;
      this.raf = requestAnimationFrame(loop);
      this.frame();
    };
    if (typeof requestAnimationFrame === 'function') this.raf = requestAnimationFrame(loop);
  }

  stop(): void {
    this.running = false;
    if (this.raf && typeof cancelAnimationFrame === 'function') cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  private frame(): void {
    const now = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    const dt = Math.min((now - this.last) / 1000, 0.05);
    this.last = now;
    this.t += dt;

    if (this.energyProvider) this.energyTarget = Math.max(0, Math.min(1, this.energyProvider()));
    else this.energyTarget *= 0.94;
    this.energy += (this.energyTarget - this.energy) * 0.12;
    for (let i = 0; i < 3; i++) this.color[i] += (this.target[i] - this.color[i]) * 0.06;

    this.render();
  }

  // ---- drawing ----
  private render(): void {
    const ctx = this.ctx;
    if (!ctx) return;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, this.w, this.h);

    const cx = this.w / 2, cy = this.h / 2;
    const R = Math.min(this.w, this.h) / 2;
    // A small floor so the light always reads as alive, never a flat disc.
    const e = Math.max(this.energy, 0.09);
    // Calm breath (≈5.5s) so the orb feels alive at rest; energy adds reach.
    const breath = 0.5 + 0.5 * Math.sin(this.t * (Math.PI * 2) / 5.5);
    const spin = this.state === 'thinking' ? this.t * 0.9 : this.t * 0.25;
    const reach = R * (0.34 + breath * 0.08 + e * 0.42);

    ctx.globalCompositeOperation = 'lighter';

    // Outer atmospheric bloom — the halo the body sits in.
    this.blob(cx, cy, R * (0.92 + e * 0.18), this.deep, 0.22 + e * 0.18);

    // Orbiting light lobes.
    const colDim = mix(this.color, this.deep, 0.35);
    for (const lo of this.lobes) {
      const a = lo.ang + spin * lo.spd + Math.sin(this.t * lo.spd * 1.7 + lo.phase) * 0.5;
      const orbit = reach * (lo.rad / 0.2);
      const wob = 1 + 0.22 * Math.sin(this.t * 1.3 + lo.phase);
      const lx = cx + Math.cos(a) * orbit * wob;
      // "thinking" lifts the cluster slightly (a contemplative tilt).
      const ly = cy + Math.sin(a) * orbit * wob - (this.state === 'thinking' ? R * 0.05 : 0);
      const size = R * lo.size * (0.34 + e * 0.22) * (0.85 + 0.3 * Math.sin(this.t + lo.phase));
      const col = mix(colDim, this.color, 0.5 + 0.5 * Math.sin(a + this.t));
      this.blob(lx, ly, Math.max(2, size), col, 0.5 + e * 0.3);
    }

    // The bright core — pale platinum heart that pulses with energy.
    const coreR = R * (0.22 + breath * 0.03 + e * 0.16);
    this.blob(cx, cy, coreR, mix(this.bright, [255, 252, 240], 0.4 + e * 0.3), 0.95);

    ctx.globalCompositeOperation = 'source-over';
  }

  private blob(x: number, y: number, r: number, c: RGB, alpha: number): void {
    const ctx = this.ctx!;
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    const [cr, cg, cb] = c;
    g.addColorStop(0, `rgba(${cr | 0},${cg | 0},${cb | 0},${alpha})`);
    g.addColorStop(0.45, `rgba(${cr | 0},${cg | 0},${cb | 0},${alpha * 0.42})`);
    g.addColorStop(1, `rgba(${cr | 0},${cg | 0},${cb | 0},0)`);
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }

  /** One calm frame for reduced-motion / non-animated contexts. */
  private renderStatic(): void {
    if (!this.ctx) return;
    this.energy = 0; this.t = 2.1;
    for (let i = 0; i < 3; i++) this.color[i] = this.target[i];
    this.render();
  }

  dispose(): void {
    this.stop();
    this.energyProvider = undefined;
  }
}
