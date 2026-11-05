// Design Level 2 shell — "The Presence": an Aura you step inside.
//
// The volumetric curl-noise smoke field (ParticleField) is the star; the shell
// wraps it in the lightest possible HUD so the experience is "communing with a
// being of light", not "using a chat app":
//   - an "Awaken" invitation (a breathing ring of light) to begin,
//   - a reactive halo centred on the presence that swells with live amplitude,
//   - a single state-of-light word (dormant · listening · thinking · speaking),
//   - a fading column of recent turns, and a molten-glass drawing surface.
//
// Three.js is loaded only when this shell is built (WS5), so Level 1 and Level 3
// never download it. Closing leaves a small orb to reopen the presence.
//
// The shell owns presentation only; the host element owns the Session and routes
// its events here. The SAME state-of-light language as L1/L3 is expressed purely
// through the colour + cadence of the smoke and halo — no extra chrome.

import { ComponentPayload, Grounding } from '../../protocol';
import { FluidBuddhaConfig } from '../../core/config';
import { Canvas } from '../components/canvas';
import { sourcesEl } from '../citations';
import type { ParticleField } from '../particles/ParticleField';
import { loadParticleField } from '../particles/load';
import { AuraState } from '../aura/AuraCanvas';
import { MessageStack } from './MessageStack';
import { t } from '../../i18n';

const ICONS = {
  play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
};

const SILVER = '#c2c8d2';

export interface Level2Controller {
  primeAudio(): void;
  connect(): void;
  startVoice(): void;
  stopVoice(): void;
  submitText(text: string): void;
  notifyRendered(syncId: string): void;
  reportComponentState?(syncId: string, patch: Record<string, unknown>): void;
  /** Live 0..1 amplitude of the user's mic and the agent's TTS playback. */
  inputLevel(): number;
  outputLevel(): number;
  /** Open a cited source page (host navigation). */
  openSource?(route: string): void;
}

export class Level2Shell {
  readonly root: HTMLDivElement;
  private particles?: ParticleField;
  private stack: MessageStack;
  private canvas: Canvas;
  private drawEl: HTMLDivElement;
  private statusEl: HTMLDivElement;
  private playBtn: HTMLButtonElement;
  private hintEl: HTMLDivElement;
  private reopenBtn: HTMLButtonElement;
  private textarea: HTMLTextAreaElement;
  private regatherTimer: ReturnType<typeof setTimeout> | null = null;
  private started = false;
  private disposed = false;
  private readonly accent: string;
  // Short-lived activity pulses so motion reacts even when the audio waveform is
  // silent (typing, or mock TTS); real voice level dominates when present.
  private userPulse = 0;
  private agentPulse = 0;
  private speaker: 'none' | 'user' | 'agent' = 'none';
  private state: AuraState = 'dormant';
  private thinking = false;
  private thinkingUntil = 0;

  constructor(
    parent: ShadowRoot,
    config: FluidBuddhaConfig,
    private readonly controller: Level2Controller,
  ) {
    this.accent = config.accent;
    const root = document.createElement('div');
    root.className = 'l2';
    root.setAttribute('data-state', 'dormant');

    root.appendChild(this.div('l2-scrim'));

    const canvasEl = document.createElement('canvas');
    canvasEl.className = 'l2-canvas';
    root.appendChild(canvasEl);

    // Reactive halo centred on the presence.
    root.appendChild(this.div('l2-halo'));

    this.statusEl = this.div('l2-status');
    this.statusEl.textContent = '';
    root.appendChild(this.statusEl);

    const close = document.createElement('button');
    close.className = 'l2-close';
    close.setAttribute('aria-label', t('close'));
    close.innerHTML = ICONS.close;
    close.addEventListener('click', () => this.hide());
    root.appendChild(close);

    // Centred drawing surface (hidden until a component arrives).
    this.drawEl = this.div('l2-draw');
    root.appendChild(this.drawEl);
    this.canvas = new Canvas(
      this.drawEl,
      (id) => this.controller.notifyRendered(id),
      (id, patch) => this.controller.reportComponentState?.(id, patch),
    );

    // Fading message stack, just above the input.
    const stackEl = this.div('l2-stack');
    root.appendChild(stackEl);
    this.stack = new MessageStack(stackEl);

    // "Awaken" invitation.
    this.playBtn = document.createElement('button');
    this.playBtn.className = 'l2-play';
    this.playBtn.setAttribute('aria-label', t('awaken', { name: 'Pragya' }));
    this.playBtn.innerHTML = ICONS.play;
    this.playBtn.addEventListener('click', () => this.onPlay());
    root.appendChild(this.playBtn);
    this.hintEl = this.div('l2-hint');
    this.hintEl.textContent = t('tapAwaken');
    root.appendChild(this.hintEl);

    // Near-transparent bottom input (always present — typing works without play).
    const inputRow = this.div('l2-input');
    this.textarea = document.createElement('textarea');
    this.textarea.placeholder = t('placeholder');
    this.textarea.setAttribute('aria-label', t('messageTo', { name: 'Pragya' }));
    this.textarea.rows = 1;
    this.textarea.addEventListener('input', () => this.onTyping());
    this.textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.submit();
      }
    });
    const send = document.createElement('button');
    send.className = 'l2-send';
    send.setAttribute('aria-label', t('send'));
    send.innerHTML = ICONS.send;
    send.addEventListener('click', () => this.submit());
    inputRow.append(this.textarea, send);
    root.appendChild(inputRow);

    parent.appendChild(root);
    this.root = root;

    // After close: a small orb that brings the presence back.
    this.reopenBtn = document.createElement('button');
    this.reopenBtn.className = 'l2-reopen l2-hidden';
    this.reopenBtn.setAttribute('aria-label', t('openAgent', { name: 'Pragya' }));
    this.reopenBtn.addEventListener('click', () => this.show());
    parent.appendChild(this.reopenBtn);

    // Particles — degrade gracefully if WebGL is unavailable (e.g. jsdom) or
    // the Three.js bundle can't be fetched; the halo still carries the state.
    const hasWebGL = typeof WebGLRenderingContext !== 'undefined';
    if (hasWebGL) {
      void loadParticleField()
        .then((Field) => {
          if (this.disposed) return;
          const particles = new Field(canvasEl, { accent: this.accent });
          particles.setEnergyProvider(() => this.computeEnergy());
          // A warm resting glow so the presence reads gold at rest (dormant).
          particles.setTint(this.accent, 0.42);
          if (this.started) particles.toBottom();
          if (!this.root.classList.contains('l2-hidden')) particles.start();
          this.particles = particles;
        })
        .catch(() => canvasEl.classList.add('l2-hidden'));
    } else {
      canvasEl.classList.add('l2-hidden');
    }

    this.onResize = this.onResize.bind(this);
    if (typeof window !== 'undefined') window.addEventListener('resize', this.onResize);
    this.bindAgentActivity();
  }

  // ---- user actions ----
  private onPlay(): void {
    this.begin();
    this.playBtn.classList.add('l2-hidden');
    this.hintEl.classList.add('l2-hidden');
    this.controller.primeAudio();
    this.controller.connect();
    this.controller.startVoice();
  }

  private onTyping(): void {
    this.userPulse = 1;
  }

  /** Combined 0..1 energy fed to the particle flow each frame: real voice
   *  amplitude plus decaying typing/agent pulses. Also resolves the
   *  state-of-light, the tint, and the reactive CSS amplitude var. */
  private computeEnergy(): number {
    const out = this.controller.outputLevel();
    const inp = this.controller.inputLevel();
    this.userPulse *= 0.93;
    this.agentPulse *= 0.93;
    const agent = Math.max(out, this.agentPulse);
    const user = Math.max(inp, this.userPulse);
    const e = Math.min(1, Math.max(agent, user));
    this.root.style.setProperty('--fb-energy', e.toFixed(3));
    this.updateTint(agent, user);
    this.updateState(agent, user);
    return e;
  }

  /** Shift colour toward the agent (gold), the user (silver), or the warm
   *  resting glow, based on who is currently active. */
  private updateTint(agent: number, user: number): void {
    let next: typeof this.speaker;
    if (agent > 0.06 && agent >= user) next = 'agent';
    else if (user > 0.06 && user > agent) next = 'user';
    else next = 'none';
    if (next === this.speaker) return;
    this.speaker = next;
    if (next === 'agent') this.particles?.setTint(this.accent, 0.9);
    else if (next === 'user') this.particles?.setTint(SILVER, 0.7);
    else this.particles?.setTint(this.accent, 0.42); // warm rest
  }

  /** Resolve the state-of-light word + the data-state used by the halo. */
  private updateState(agent: number, user: number): void {
    const now = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    let next: AuraState;
    if (agent > 0.06) next = 'speaking';
    else if (user > 0.06) next = 'listening';
    else if (this.thinking && now < this.thinkingUntil) next = 'thinking';
    else next = this.started ? 'listening' : 'dormant';
    if (next === this.state) return;
    this.state = next;
    this.root.setAttribute('data-state', next);
    if (this.started) {
      this.statusEl.textContent =
        next === 'speaking' ? 'speaking' : next === 'thinking' ? 'thinking' : 'listening';
    }
  }

  private submit(): void {
    const text = this.textarea.value.trim();
    if (!text) return;
    this.begin();
    this.controller.submitText(text);
    this.textarea.value = '';
  }

  /** First interaction: dismiss the invitation, awaken the halo, gather smoke. */
  private begin(): void {
    if (this.started) return;
    this.started = true;
    this.playBtn.classList.add('l2-hidden');
    this.hintEl.classList.add('l2-hidden');
    this.root.classList.add('awake');
    this.particles?.toBottom();
  }

  // ---- session-driven updates (called by the host element) ----
  setStatus(s: string): void {
    if (s === 'failed') this.statusEl.textContent = t('textMode');
    else if (s === 'open' && this.started && !this.statusEl.textContent) this.statusEl.textContent = t('listening');
  }

  setTourStatus(text: string): void {
    if (text) {
      this.begin();
      this.statusEl.textContent = t('guidedTour');
    }
  }

  userMessage(text: string): void {
    this.canvas.clear();
    this.drawEl.classList.remove('show');
    this.stack.push(text, 'user');
    this.particles?.toBottom();
    this.userPulse = 1;
    this.thinking = true;
    this.thinkingUntil = (typeof performance !== 'undefined' ? performance.now() : Date.now()) + 6000;
  }

  agentMessage(text: string, grounding?: Grounding): void {
    this.stack.push(text, 'agent', sourcesEl(grounding, this.controller.openSource));
    this.agentPulse = Math.max(this.agentPulse, 0.7);
    this.thinking = false;
  }

  agentAudioTick(): void {
    this.agentPulse = Math.max(this.agentPulse, 0.5);
    this.thinking = false;
  }

  addComponent(payload: ComponentPayload): void {
    this.drawEl.classList.add('show');
    this.canvas.add(payload);
    this.thinking = false;
    this.agentActivity(2600);
  }

  patch(syncId: string, patch: Record<string, unknown>): void {
    this.canvas.applyPatch(syncId, patch);
  }

  systemMessage(msg: string): void {
    this.statusEl.textContent = msg;
  }

  // ---- particle choreography for agent activity (req vi) ----
  private bindAgentActivity(): void {
    if (typeof window === 'undefined') return;
    const onAct = () => this.agentActivity(1600);
    window.addEventListener('fluidbuddha:navigate', onAct);
    window.addEventListener('fluidbuddha:scroll_to', onAct);
    this._unbindActivity = () => {
      window.removeEventListener('fluidbuddha:navigate', onAct);
      window.removeEventListener('fluidbuddha:scroll_to', onAct);
    };
  }
  private _unbindActivity: (() => void) | null = null;

  private agentActivity(durationMs: number): void {
    if (!this.particles) return;
    this.particles.toSpread();
    if (this.regatherTimer) clearTimeout(this.regatherTimer);
    this.regatherTimer = setTimeout(() => this.particles?.toBottom(), durationMs / 2);
  }

  private onResize(): void {
    this.particles?.resize();
  }

  hide(): void {
    this.controller.stopVoice();
    this.root.classList.add('l2-hidden');
    this.reopenBtn.classList.remove('l2-hidden');
    this.particles?.stop(); // no rendering while closed
  }

  /** Reopen after close. Voice stays off until the visitor taps to talk. */
  show(): void {
    this.root.classList.remove('l2-hidden');
    this.reopenBtn.classList.add('l2-hidden');
    this.particles?.start();
    this.particles?.resize();
    if (this.started) {
      this.hintEl.textContent = t('tapTalk');
      this.playBtn.classList.remove('l2-hidden');
      this.hintEl.classList.remove('l2-hidden');
    }
    this.textarea.focus();
  }

  // ---- helpers ----
  private div(cls: string): HTMLDivElement {
    const d = document.createElement('div');
    d.className = cls;
    return d;
  }

  dispose(): void {
    this.disposed = true;
    this.reopenBtn.remove();
    if (this.regatherTimer) clearTimeout(this.regatherTimer);
    this._unbindActivity?.();
    if (typeof window !== 'undefined') window.removeEventListener('resize', this.onResize);
    this.particles?.dispose();
  }
}
