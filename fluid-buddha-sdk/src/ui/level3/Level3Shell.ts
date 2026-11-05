// Design Level 3 shell — "The Atmosphere": an Aura dissolved into the page.
//
// There is no widget. Pragya becomes the light in the room:
//   • a breathing rim-light at the edge of vision that pulses with her state,
//   • a spotlight that dims the page and illuminates whatever she references as
//     she scrolls/navigates (driven by the host bridge's `fluidbuddha:*` events),
//   • her words as ephemeral glass captions anchored to the page, and
//   • a ⌘K / light-mote summon — invoke, speak, and the atmosphere takes over.
//
// The overlay itself is pointer-transparent so the host page stays fully usable;
// only the summon, captions and the mote capture input. Same state-of-light
// language as L1/L2 — colour + cadence carry meaning, never chrome.

import { ComponentPayload, Grounding } from '../../protocol';
import { FluidBuddhaConfig } from '../../core/config';
import { Canvas } from '../components/canvas';
import { sourcesEl } from '../citations';
import { AuraCanvas, AuraState } from '../aura/AuraCanvas';
import { t } from '../../i18n';

const ICONS = {
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
};

export interface Level3Controller {
  primeAudio(): void;
  connect(): void;
  startVoice(): void;
  stopVoice(): void;
  submitText(text: string): void;
  notifyRendered(syncId: string): void;
  reportComponentState?(syncId: string, patch: Record<string, unknown>): void;
  inputLevel(): number;
  outputLevel(): number;
  /** Open a cited source page (host navigation). */
  openSource?(route: string): void;
}

const MAX_CAPTIONS = 4;
const CAPTION_TTL = 14000;     // ms a caption lingers before fading out
const SPOTLIGHT_TTL = 4200;    // ms the spotlight holds on a referenced section

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export class Level3Shell {
  readonly root: HTMLDivElement;
  private auraEl: HTMLDivElement;
  private veilEl: HTMLDivElement;
  private ringEl: HTMLDivElement;
  private capsEl: HTMLDivElement;
  private drawEl: HTMLDivElement;
  private summonEl: HTMLDivElement;
  private summonInput: HTMLTextAreaElement;
  private orb?: AuraCanvas;
  private canvas: Canvas;

  private readonly accent: string;
  private readonly reduce: boolean;
  private awake = false;
  private summoning = false;
  private state: AuraState = 'dormant';
  private thinking = false;
  private thinkingUntil = 0;
  private speakingUntil = 0;
  private agentPulse = 0;
  private reactRaf = 0;
  private spotlightTimer: ReturnType<typeof setTimeout> | null = null;
  private unbind: Array<() => void> = [];

  constructor(
    parent: ShadowRoot,
    config: FluidBuddhaConfig,
    private readonly controller: Level3Controller,
  ) {
    this.accent = config.accent;
    this.reduce = prefersReducedMotion();

    const root = document.createElement('div');
    root.className = 'l3';
    root.setAttribute('data-state', 'dormant');

    this.auraEl = this.div('l3-aura');
    this.veilEl = this.div('l3-veil');
    this.ringEl = this.div('l3-ring');
    this.capsEl = this.div('l3-caps');
    this.drawEl = this.div('l2-draw');          // reuse the centred molten-glass holder
    root.append(this.auraEl, this.veilEl, this.ringEl, this.capsEl, this.drawEl);

    this.canvas = new Canvas(
      this.drawEl,
      (id) => this.controller.notifyRendered(id),
      (id, patch) => this.controller.reportComponentState?.(id, patch),
    );

    // The summon — a centred Aura + prompt, behind a soft backdrop.
    const backdrop = this.div('l3-summon-backdrop');
    backdrop.addEventListener('click', () => this.dismissSummon());
    root.appendChild(backdrop);

    this.summonEl = this.div('l3-summon');
    const orbCanvas = document.createElement('canvas');
    orbCanvas.className = 'l3-orb';
    this.summonEl.appendChild(orbCanvas);
    const inputWrap = this.div('l3-summon-input');
    this.summonInput = document.createElement('textarea');
    this.summonInput.rows = 1;
    this.summonInput.placeholder = t('askAnything');
    this.summonInput.setAttribute('aria-label', t('ask'));
    this.summonInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.submit(); }
      else if (e.key === 'Escape') this.dismissSummon();
    });
    const send = document.createElement('button');
    send.className = 'l3-summon-send';
    send.setAttribute('aria-label', t('send'));
    send.innerHTML = ICONS.send;
    send.addEventListener('click', () => this.submit());
    inputWrap.append(this.summonInput, send);
    const hint = this.div('l3-summon-hint');
    hint.innerHTML = t('pressKey', { key: '<kbd>' + (this.isMac() ? '⌘' : 'Ctrl') + ' K</kbd>' });
    this.summonEl.append(inputWrap, hint);
    root.appendChild(this.summonEl);

    // A persistent mote of light — the minimal, ambient invocation affordance.
    const seed = document.createElement('button');
    seed.className = 'l3-seed';
    seed.setAttribute('aria-label', t('summon'));
    seed.addEventListener('click', () => this.summon());
    root.appendChild(seed);

    parent.appendChild(root);
    this.root = root;

    if (orbCanvas) {
      this.orb = new AuraCanvas(orbCanvas, { accent: this.accent, reducedMotion: this.reduce });
      this.orb.setEnergyProvider(() => Math.max(this.controller.inputLevel(), this.controller.outputLevel()));
    }

    this.bindGlobal();
    if (config.autoStart) setTimeout(() => this.summon(), 400);
  }

  private isMac(): boolean {
    return typeof navigator !== 'undefined' && /mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent || '');
  }

  // ---- summon ----
  private bindGlobal(): void {
    if (typeof window === 'undefined') return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        this.summoning ? this.dismissSummon() : this.summon();
      } else if (e.key === 'Escape' && this.summoning) {
        this.dismissSummon();
      }
    };
    const onScroll = (e: Event) => this.onScrollTo((e as CustomEvent).detail || {});
    const onNav = () => this.flashAura();
    window.addEventListener('keydown', onKey);
    window.addEventListener('fluidbuddha:scroll_to', onScroll as EventListener);
    window.addEventListener('fluidbuddha:navigate', onNav);
    this.unbind.push(
      () => window.removeEventListener('keydown', onKey),
      () => window.removeEventListener('fluidbuddha:scroll_to', onScroll as EventListener),
      () => window.removeEventListener('fluidbuddha:navigate', onNav),
    );
  }

  summon(): void {
    this.awaken();
    this.summoning = true;
    this.root.classList.add('summoning');
    this.orb?.start();
    this.controller.primeAudio();
    this.controller.connect();
    this.controller.startVoice();
    setTimeout(() => { try { this.summonInput.focus(); } catch { /* noop */ } }, 60);
  }

  private dismissSummon(): void {
    this.summoning = false;
    this.root.classList.remove('summoning');
    // The conversation persists ambiently through the edge-aura + captions.
  }

  /** Bring the atmosphere to life (edge-aura on, reactive loop running). */
  private awaken(): void {
    if (this.awake) return;
    this.awake = true;
    this.root.classList.add('awake');
    this.startReactiveLoop();
  }

  private submit(): void {
    const text = this.summonInput.value.trim();
    if (!text) return;
    this.awaken();
    this.controller.submitText(text);
    this.summonInput.value = '';
    this.dismissSummon();
  }

  // ---- reactive state-of-light loop ----
  private startReactiveLoop(): void {
    if (this.reduce || typeof requestAnimationFrame !== 'function' || this.reactRaf) return;
    const tick = () => {
      if (!this.awake) { this.reactRaf = 0; return; }
      this.reactRaf = requestAnimationFrame(tick);
      const inL = this.controller.inputLevel();
      const outL = this.controller.outputLevel();
      this.agentPulse *= 0.93;
      const out = Math.max(outL, this.agentPulse);
      this.root.style.setProperty('--fb-energy', Math.max(inL, out).toFixed(3));
      const now = (typeof performance !== 'undefined' ? performance.now() : Date.now());
      if (out > 0.05) this.speakingUntil = now + 600;
      let next: AuraState;
      if (now < this.speakingUntil) next = 'speaking';                   // she imparts — warm gold
      else if (this.thinking && now < this.thinkingUntil) next = 'thinking'; // she contemplates
      else if (inL > 0.05) next = 'listening';                          // you speak — cool silver
      else next = 'dormant';                                            // present, at rest — warm gold
      this.setState(next);
    };
    this.reactRaf = requestAnimationFrame(tick);
  }

  private setState(s: AuraState): void {
    if (s === this.state) return;
    this.state = s;
    this.root.setAttribute('data-state', s);
    this.orb?.setState(s);
  }

  // ---- spotlight ----
  private onScrollTo(detail: { sectionId?: string; direction?: string }): void {
    this.flashAura();
    const el = detail.sectionId ? this.resolveSection(detail.sectionId) : null;
    if (!el) return;
    // Let the host's smooth-scroll settle, then illuminate the final position.
    setTimeout(() => this.spotlight(el), 560);
  }

  private spotlight(el: Element): void {
    if (this.reduce) return;
    const r = el.getBoundingClientRect();
    if (!r.width && !r.height) return;
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    const radius = Math.max(r.width, r.height) / 2 + 150;
    const s = this.root.style;
    s.setProperty('--l3-x', `${cx}px`);
    s.setProperty('--l3-y', `${cy}px`);
    s.setProperty('--l3-r', `${radius}px`);
    s.setProperty('--l3-rx', `${r.left - 10}px`);
    s.setProperty('--l3-ry', `${r.top - 10}px`);
    s.setProperty('--l3-rw', `${r.width + 20}px`);
    s.setProperty('--l3-rh', `${r.height + 20}px`);
    this.root.classList.add('spotlight');
    if (this.spotlightTimer) clearTimeout(this.spotlightTimer);
    this.spotlightTimer = setTimeout(() => this.root.classList.remove('spotlight'), SPOTLIGHT_TTL);
  }

  /** Mirror the bridge's loose section resolution: id → id-substring → heading. */
  private resolveSection(raw: string): Element | null {
    if (typeof document === 'undefined') return null;
    const id = raw.replace(/^#/, '');
    try {
      const byId = document.getElementById(id);
      if (byId) return byId;
      const needle = id.replace(/[-_]/g, ' ').toLowerCase().trim();
      if (!needle) return null;
      const idMatch = Array.from(document.querySelectorAll('[id]')).find((e) =>
        e.id.replace(/[-_]/g, ' ').toLowerCase().includes(needle));
      if (idMatch) return idMatch;
      const heads = Array.from(document.querySelectorAll('h1,h2,h3,h4'));
      const head = heads.find((e) => (e.textContent || '').toLowerCase().includes(needle));
      return (head?.closest('section') as Element) || head || null;
    } catch {
      return null;
    }
  }

  /** A brief brightening of the edge-aura on any agent action. */
  private flashAura(): void {
    this.agentPulse = Math.max(this.agentPulse, 0.6);
  }

  // ---- captions ----
  private pushCaption(text: string, who: 'user' | 'agent', grounding?: Grounding): void {
    if (!text.trim()) return;
    const cap = document.createElement('div');
    cap.className = `l3-cap fb-glass ${who}`;
    cap.append(this.div2(undefined, text));
    const sources = sourcesEl(grounding, this.controller.openSource);
    if (sources) cap.appendChild(sources);
    this.capsEl.appendChild(cap);
    while (this.capsEl.childElementCount > MAX_CAPTIONS) {
      this.capsEl.firstElementChild?.remove();
    }
    // Ephemeral: each caption fades and removes itself so the page stays calm.
    setTimeout(() => {
      cap.style.opacity = '0';
      cap.style.transform = 'translateY(-8px)';
      setTimeout(() => cap.remove(), 700);
    }, CAPTION_TTL);
  }

  // ---- session-driven updates (same contract as the host wiring) ----
  setStatus(_s: string): void { /* state is shown through the light, not text */ }

  setTourStatus(text: string): void {
    if (text) { this.awaken(); this.flashAura(); }
  }

  userMessage(text: string): void {
    this.awaken();
    this.canvas.clear();
    this.drawEl.classList.remove('show');
    this.dismissSummon();
    this.pushCaption(text, 'user');
    this.thinking = true;
    this.thinkingUntil = (typeof performance !== 'undefined' ? performance.now() : Date.now()) + 6000;
  }

  agentMessage(text: string, grounding?: Grounding): void {
    this.pushCaption(text, 'agent', grounding);
    this.flashAura();
    this.thinking = false;
  }

  agentAudioTick(): void {
    this.agentPulse = Math.max(this.agentPulse, 0.5);
    this.thinking = false;
  }

  addComponent(payload: ComponentPayload): void {
    this.awaken();
    this.drawEl.classList.add('show');
    this.canvas.add(payload);
    this.flashAura();
    this.thinking = false;
  }

  patch(syncId: string, patch: Record<string, unknown>): void {
    this.canvas.applyPatch(syncId, patch);
  }

  systemMessage(msg: string): void {
    this.pushCaption(msg, 'agent');
  }

  // ---- helpers ----
  private div(cls: string): HTMLDivElement {
    const d = document.createElement('div');
    d.className = cls;
    return d;
  }
  private div2(cls: string | undefined, text: string): HTMLDivElement {
    const d = document.createElement('div');
    if (cls) d.className = cls;
    d.textContent = text;
    return d;
  }

  dispose(): void {
    if (this.reactRaf && typeof cancelAnimationFrame === 'function') cancelAnimationFrame(this.reactRaf);
    if (this.spotlightTimer) clearTimeout(this.spotlightTimer);
    this.unbind.forEach((fn) => fn());
    this.unbind = [];
    this.orb?.dispose();
  }
}
