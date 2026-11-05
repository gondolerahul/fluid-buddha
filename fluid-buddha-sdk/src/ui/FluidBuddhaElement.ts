// <fluid-buddha> — the framework-agnostic Web Component. All UI lives in a
// Shadow DOM so it never collides with the host page's CSS/JS (Req 3.1.2/4.1).
//
// Design Level 1 — "The Companion": Pragya is a living Aura you hold. The
// launcher is a breathing light-form (a 2D AuraCanvas, no WebGL), the panel is
// molten obsidian glass with a gold light-seam, and the agent's state —
// dormant · listening · thinking · speaking — is read through how that light
// behaves, mirrored on the avatar. Voice is the hero; typing is the quiet path.

import { Grounding, PageSpec } from '../protocol';
import {
  DESIGN_LEVELS, FluidBuddhaConfig, FluidBuddhaOptions, optionsFromAttributes, resolveConfig,
} from '../core/config';
import { HostBridge } from '../core/HostBridge';
import { Arm, Experiment } from '../core/Experiment';
import { TriggerRule, Triggers } from '../core/Triggers';
import { Session } from '../core/Session';
import { applyTokens, fetchDesignSystem } from '../core/designSystem';
import { Canvas } from './components/canvas';
import { sourcesEl } from './citations';
import { Level2Shell } from './level2/Level2Shell';
import { Level3Shell } from './level3/Level3Shell';
import { PageRenderer, EnquiryPayload } from './page/PageRenderer';
import { AuraCanvas, AuraState } from './aura/AuraCanvas';
import { stylesFor } from './styles';
import { callBar, callPrompt } from './call';
import { consentPrompt } from './consent';
import { actionPrompt } from './actionCard';
import { showNudge } from './nudge';
import { Lang, getLang, pickLang, prepareLang, setLang, t } from '../i18n';

const ICONS = {
  mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
};

function h<K extends keyof HTMLElementTagNameMap>(
  tag: K, className?: string, text?: string,
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text) el.textContent = text;
  return el;
}

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export class FluidBuddhaElement extends HTMLElement {
  static readonly tagName = 'fluid-buddha';

  private _options: FluidBuddhaOptions = {};
  private config!: FluidBuddhaConfig;
  private session!: Session;
  private hostBridge?: HostBridge;
  private canvas!: Canvas;
  private level2?: Level2Shell;
  private level3?: Level3Shell;
  private pageRenderer?: PageRenderer;
  private pageSurface?: HTMLDivElement;

  private trigger!: HTMLButtonElement;
  private triggerAura?: AuraCanvas;
  private avatarAura?: AuraCanvas;
  private panel!: HTMLDivElement;
  private messagesEl!: HTMLDivElement;
  private canvasEl!: HTMLDivElement;
  private statusEl!: HTMLSpanElement;
  private micBtn!: HTMLButtonElement;
  private thinkingEl: HTMLDivElement | null = null;
  private textarea!: HTMLTextAreaElement;
  private built = false;
  private experiment?: Experiment;
  /** Proactive triggers (M2-3), for keyed sites. */
  private triggers?: Triggers;
  /** The visitor has started talking this page view (no more nudges). */
  private talked = false;
  /** The embed chose its design level (data-design / options). */
  private designSet = false;
  private accentSet = false;
  /** The greeting is the site's fixed one, which the server also speaks on
   *  open: show it once (level 1 already shows it as the first message). */
  private greetEcho = false;
  private open = false;

  // ---- state-of-light machine ----
  private auraState: AuraState = 'dormant';
  private connText = '';
  private thinking = false;
  private speakingUntil = 0;
  private reactRaf = 0;

  /** Programmatic config (used by FluidBuddha.init). Merged over attributes. */
  set options(opts: FluidBuddhaOptions) {
    this._options = opts;
    if (this.built) this.config = resolveConfig({ ...optionsFromAttributes(this), ...this._options });
  }

  connectedCallback(): void {
    if (this.built) return;
    const opts = { ...optionsFromAttributes(this), ...this._options };
    this.designSet = !!opts.design;
    this.accentSet = !!opts.accent;
    this.config = resolveConfig(opts);
    this.style.setProperty('--fb-accent', this.config.accent);
    this.setAttribute('data-position', this.config.position);
    this.setAttribute('data-design', this.config.design);
    this.built = true;

    // Holdout A/B (WS11): a keyed site may be running an experiment, in which
    // case some visitors don't get the agent at all. Decide before drawing.
    const exp = new Experiment(this.config);
    this.experiment = exp;
    if (!exp.eligible) {
      this.show();
      return;
    }
    const cached = exp.cached();
    if (cached) {
      this.decide(cached);
      void exp.enroll(); // refresh for the next page view
      return;
    }
    void exp.enroll().then((arm) => this.decide(arm));
  }

  /** null: no experiment; holdout: measured, but no widget. */
  private decide(arm: Arm | null): void {
    if (arm) this.experiment?.start();
    if (arm === 'holdout') {
      this.setAttribute('data-holdout', '');
      return;
    }
    if (this.experiment) this.adopt(this.experiment, arm);
    this.show();
  }

  /** Apply the visitor's test variant, else the site's defaults (M2-4). */
  private adopt(exp: Experiment, arm: Arm | null): void {
    const c = this.config;
    const o = exp.overrides;
    const d = exp.defaults;
    const design = o.design || (!this.designSet && d.design);
    if (design && DESIGN_LEVELS.includes(design)) {
      c.design = design;
      this.setAttribute('data-design', design);
    }
    // A plugin install carries only the key: the site's colour comes from here.
    if (!this.accentSet && d.accent && /^#[0-9a-f]{3,8}$/i.test(d.accent)) {
      c.accent = d.accent;
      this.style.setProperty('--fb-accent', d.accent);
    }
    if (typeof o.tour === 'boolean') c.tour = o.tour;
    const greeting = o.greeting || d.greeting;
    if (greeting) {
      c.greeting = greeting;
      this.greetEcho = true;
    }
    if (o.triggers) c.triggerIds = o.triggers;
    if (arm && arm !== 'agent' && exp.id) c.exp = { id: exp.id, arm };
  }

  private show(): void {
    // The widget's language (M2-7): the embed's choice, the site's setting, or
    // the visitor's browser. Hindi words are fetched first (English if they
    // can't be); English shows at once.
    const site = this.experiment?.eligible ? this.experiment.defaults : null;
    if (site?.starters?.length) this.config.starters = site.starters.slice(0, 4);
    if (pickLang(this.config.lang, site) === 'hi') {
      void prepareLang('hi').then((lang) => this.reveal(lang, site?.greeting_hi));
    } else {
      setLang('en');
      this.reveal('en');
    }
  }

  private reveal(lang: Lang, greetingHi?: string | null): void {
    // A Hindi visitor gets the site's Hindi greeting (the server speaks the
    // same words), else the default one in Hindi — unless the embed set one.
    if (lang === 'hi' && !this._options.greeting && !optionsFromAttributes(this).greeting) {
      this.config.greeting = greetingHi || '';
      this.greetEcho = !!greetingHi;
    }
    if (!this.config.greeting) this.config.greeting = t('greeting');
    this.build();
    if (this.config.design === 'level1' && this.config.autoStart) {
      requestAnimationFrame(() => this.openPanel());
    }
    this.triggers = new Triggers(this.config, this.experiment?.visitorId ?? null,
      (rule) => this.onTrigger(rule), () => this.open || this.talked);
    void this.triggers.start();
  }

  // ---- proactive triggers (M2-3) ----
  private onTrigger(rule: TriggerRule): void {
    const root = this.shadowRoot;
    if (!root || !this.triggers) return;
    if (rule.action === 'open') {
      this.triggers.clickedRule(rule);
      this.openWith(rule.message);
      return;
    }
    showNudge(root, rule.message,
      () => { this.triggers?.clickedRule(rule); this.openWith(rule.message); },
      () => this.triggers?.dismissed(rule));
  }

  /** Open the agent showing `message` as its first words (no audio). */
  private openWith(message: string): void {
    this.session?.skipWelcome();
    if (this.config.design === 'level2') {
      this.level2?.show();
      this.level2?.agentMessage(message);
    } else if (this.config.design === 'level3') {
      this.level3?.summon();
      this.level3?.agentMessage(message);
    } else {
      this.openPanel();
      this.addMessage('pragya', message);
    }
  }

  disconnectedCallback(): void {
    if (this.reactRaf) cancelAnimationFrame(this.reactRaf);
    this.triggerAura?.dispose();
    this.avatarAura?.dispose();
    this.level2?.dispose();
    this.level3?.dispose();
    this.session?.destroy();
    this.experiment?.stop();
    this.triggers?.stop();
  }

  // ---- build the shadow UI ----
  private build(): void {
    const root = this.attachShadow({ mode: 'open' });
    const style = document.createElement('style');
    style.textContent = stylesFor(this.config.design, this.config.intelligence === 'extreme');
    root.appendChild(style);

    // A single film-grain film over the whole overlay — the "shot on film" luxe.
    root.appendChild(h('div', 'fb-grain'));

    if (this.config.intelligence === 'extreme') this.setupPageSurface(root);

    if (this.config.design === 'level2') { this.buildLevel2(root); return; }
    if (this.config.design === 'level3') { this.buildLevel3(root); return; }
    this.buildPanel(root);
  }

  // ---- Extreme: runtime-generated full-page surface ----
  private setupPageSurface(root: ShadowRoot): void {
    const surface = document.createElement('div');
    surface.className = 'fbpage hidden';

    const bar = document.createElement('div');
    bar.className = 'fbpage-bar';
    bar.append(h('div', 'fbpage-brand', 'Pragya'));
    const back = h('button', 'fbpage-back', t('close'));
    back.addEventListener('click', () => surface.classList.add('hidden'));
    bar.append(back);

    const inner = h('div', 'fbpage-inner');
    surface.append(bar, inner);
    root.appendChild(surface);

    this.pageSurface = surface;
    this.pageRenderer = new PageRenderer(inner, (p) => this.onEnquiry(p));

    void fetchDesignSystem(this.config.api, this.config.site).then((ds) => {
      if (ds) {
        applyTokens(surface, ds.tokens);
        const brand = bar.querySelector('.fbpage-brand');
        if (brand && ds.name) brand.textContent = ds.name;
      }
    });
  }

  private renderPage(page: PageSpec): void {
    if (!this.pageRenderer || !this.pageSurface) return;
    this.pageSurface.classList.remove('hidden');
    this.pageRenderer.render(page);
  }

  /** The generated enquiry form posts straight to /leads (WS7) — the visitor's
   *  details are stored and delivered without passing through the LLM. */
  private async onEnquiry(payload: EnquiryPayload): Promise<boolean> {
    const ok = await this.session.submitLead(payload.values);
    if (ok) this.addMessage('pragya', t('thanks'));
    else this.addMessage('system', t('sendFailed'));
    return ok;
  }

  // ---- Design Level 2: immersive particle overlay ----
  private buildLevel2(root: ShadowRoot): void {
    const bridge = new HostBridge(this.config.hooks, this.config.navigation);
    const shell = new Level2Shell(root, this.config, {
      primeAudio: () => this.session.primeAudio(),
      connect: () => this.session.connect(),
      startVoice: () => { this.noteTalk(); void this.session.startVoice(); },
      stopVoice: () => this.session.stopVoice(),
      submitText: (text) => this.submitText(text),
      notifyRendered: (id) => this.session.notifyRendered(id),
      reportComponentState: (id, patch) => this.session.reportComponentState(id, patch),
      inputLevel: () => this.session.inputLevel(),
      outputLevel: () => this.session.outputLevel(),
      openSource: (route) => bridge.navigate(route),
    });
    this.level2 = shell;

    this.session = new Session(this.config, bridge, {
      onStatus: (s) => shell.setStatus(s),
      onUserTranscript: (text, interim) => { if (!interim && text) shell.userMessage(text); },
      onAgentMessage: (text, grounding) => shell.agentMessage(text, grounding),
      onComponent: (c) => shell.addComponent(c),
      onPatch: (sid, patch) => shell.patch(sid, patch),
      onSystem: (msg) => shell.systemMessage(msg),
      onPage: (p) => this.renderPage(p),
      onAgentAudio: () => shell.agentAudioTick(),
      onTourStatus: (text) => shell.setTourStatus(text),
      requestConsent: (p) => consentPrompt(root, p),
      requestCall: (name) => callPrompt(root, name),
      onCall: callBar(root),
      onProposal: (c, answer) => actionPrompt(root, c, answer),
    });
    this.session.enableWelcome(() => this.pageContext());
  }

  // ---- Design Level 3: ambient atmosphere (no widget) ----
  private buildLevel3(root: ShadowRoot): void {
    const bridge = new HostBridge(this.config.hooks, this.config.navigation);
    const shell = new Level3Shell(root, this.config, {
      primeAudio: () => this.session.primeAudio(),
      connect: () => this.session.connect(),
      startVoice: () => { this.noteTalk(); void this.session.startVoice(); },
      stopVoice: () => this.session.stopVoice(),
      submitText: (text) => this.submitText(text),
      notifyRendered: (id) => this.session.notifyRendered(id),
      reportComponentState: (id, patch) => this.session.reportComponentState(id, patch),
      inputLevel: () => this.session.inputLevel(),
      outputLevel: () => this.session.outputLevel(),
      openSource: (route) => bridge.navigate(route),
    });
    this.level3 = shell;

    this.session = new Session(this.config, bridge, {
      onStatus: (s) => shell.setStatus(s),
      onUserTranscript: (text, interim) => { if (!interim && text) shell.userMessage(text); },
      onAgentMessage: (text, grounding) => shell.agentMessage(text, grounding),
      onComponent: (c) => shell.addComponent(c),
      onPatch: (sid, patch) => shell.patch(sid, patch),
      onSystem: (msg) => shell.systemMessage(msg),
      onPage: (p) => this.renderPage(p),
      onAgentAudio: () => shell.agentAudioTick(),
      onTourStatus: (text) => shell.setTourStatus(text),
      requestConsent: (p) => consentPrompt(root, p),
      requestCall: (name) => callPrompt(root, name),
      onCall: callBar(root),
      onProposal: (c, answer) => actionPrompt(root, c, answer),
    });
    this.session.enableWelcome(() => this.pageContext());
  }

  // ---- Design Level 1: the Companion ----
  private buildPanel(root: ShadowRoot): void {
    const reduce = prefersReducedMotion();

    // — Launcher: a living Aura, not a button with an icon —
    this.trigger = h('button', 'trigger');
    this.trigger.setAttribute('aria-label', t('talkTo', { name: 'Pragya' }));
    const triggerCanvas = document.createElement('canvas');
    triggerCanvas.className = 'trigger-aura';
    this.trigger.append(triggerCanvas);
    this.trigger.addEventListener('click', () => this.toggle());
    if (!reduce) this.bindMagnetic(this.trigger);
    root.appendChild(this.trigger);

    // — Panel: molten obsidian with a gold light-seam —
    this.panel = h('div', 'panel hidden');
    this.panel.setAttribute('data-state', 'dormant');
    const header = h('div', 'header');
    const profile = h('div', 'profile');
    const avatar = h('div', 'avatar');
    const avatarCanvas = document.createElement('canvas');
    avatar.append(avatarCanvas);
    const info = h('div');
    info.append(h('div', 'name', 'Pragya'));
    this.statusEl = h('span', 'status');
    this.statusEl.append(h('span', 'dot'), document.createTextNode(' ' + t('online')));
    info.append(this.statusEl);
    profile.append(avatar, info);
    const closeBtn = h('button', 'icon-btn');
    closeBtn.setAttribute('aria-label', t('close'));
    closeBtn.innerHTML = ICONS.close;
    closeBtn.addEventListener('click', () => this.close());
    header.append(profile, closeBtn);
    this.panel.append(header);

    // — Messages + generative canvas —
    this.messagesEl = h('div', 'messages');
    this.canvasEl = h('div', 'canvas');
    this.messagesEl.append(this.canvasEl);
    this.panel.append(this.messagesEl);

    // — Suggestion seeds —
    const chips = h('div', 'chips');
    // The site's own starter questions (English), else the built-in ones.
    const starters = getLang() === 'en' && this.config.starters?.length ? this.config.starters
      : [t('chipPricing'), t('chipIntegrate'), t('chipTour')];
    starters.forEach((label) => {
      const c = h('button', 'chip', label);
      c.addEventListener('click', () => this.submitText(label));
      chips.append(c);
    });
    this.panel.append(chips);

    // — Input row: mic is the hero —
    const inputRow = h('div', 'input');
    this.textarea = h('textarea');
    this.textarea.placeholder = t('placeholder');
    this.textarea.setAttribute('aria-label', t('messageTo', { name: 'Pragya' }));
    this.textarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.submitText(this.textarea.value);
        this.textarea.value = '';
      }
    });
    this.micBtn = h('button', 'in-btn');
    this.micBtn.innerHTML = ICONS.mic;
    this.micBtn.title = t('voiceTitle');
    this.micBtn.setAttribute('aria-label', t('toggleVoice'));
    this.micBtn.addEventListener('click', () => this.toggleVoice());
    if (!this.voiceEnabled) this.micBtn.classList.add('hidden');
    const sendBtn = h('button', 'in-btn');
    sendBtn.innerHTML = ICONS.send;
    sendBtn.title = t('send');
    sendBtn.setAttribute('aria-label', t('send'));
    sendBtn.addEventListener('click', () => {
      this.submitText(this.textarea.value);
      this.textarea.value = '';
    });
    inputRow.append(this.textarea, this.micBtn, sendBtn);
    this.panel.append(inputRow);

    root.appendChild(this.panel);

    // Wire the session
    const bridge = new HostBridge(this.config.hooks, this.config.navigation);
    this.hostBridge = bridge;
    this.canvas = new Canvas(
      this.canvasEl,
      (id) => this.session.notifyRendered(id),
      (id, patch) => this.session.reportComponentState(id, patch),
    );
    this.session = new Session(this.config, bridge, {
      onStatus: (s) => {
        this.connText = t(s === 'open' ? 'voiceReady' : s === 'failed' ? 'textMode' : 'online');
        if (this.auraState === 'dormant') this.updateStatusText();
      },
      onUserTranscript: (text, interim) => {
        if (interim) return;
        this.canvas.clear();
        if (text) {
          this.addMessage('user', text);
          this.showThinking();
        }
      },
      onAgentMessage: (text, grounding) => {
        this.hideThinking();
        if (this.greetEcho && text === this.config.greeting) this.greetEcho = false;
        else this.addMessage('pragya', text, grounding);
        this.markSpeaking();
      },
      onComponent: (c) => { this.hideThinking(); this.canvas.add(c); this.markSpeaking(); this.scrollDown(); },
      onPatch: (sid, patch) => this.canvas.applyPatch(sid, patch),
      onSystem: (msg) => { this.hideThinking(); this.addMessage('system', msg); },
      requestConsent: (p) => consentPrompt(root, p),
      requestCall: (name) => callPrompt(root, name),
      onCall: callBar(root),
      onProposal: (c, answer) => actionPrompt(root, c, answer),
      onPage: (p) => { this.hideThinking(); this.renderPage(p); },
      onAgentAudio: () => this.markSpeaking(),
      onTourStatus: (text) => { this.connText = t(text ? 'guidedTour' : 'online'); if (this.auraState === 'dormant') this.updateStatusText(); },
    });

    // The living light — launcher + avatar share the same energy provider so
    // they breathe with the conversation.
    const energy = () => Math.max(this.session.inputLevel(), this.session.outputLevel());
    this.triggerAura = new AuraCanvas(triggerCanvas, { accent: this.config.accent, reducedMotion: reduce });
    this.triggerAura.start();
    this.avatarAura = new AuraCanvas(avatarCanvas, { accent: this.config.accent, reducedMotion: reduce });
    this.avatarAura.setEnergyProvider(energy);
    this.avatarAura.start();

    this.session.enableWelcome(() => this.pageContext());
    this.addMessage('pragya', this.config.greeting);
  }

  /** Magnetic micro-physics: the launcher leans toward the cursor. Driven by
   *  direct transform writes (no per-frame React-style state) for 60fps. */
  private bindMagnetic(btn: HTMLButtonElement): void {
    const onMove = (e: PointerEvent) => {
      const r = btn.getBoundingClientRect();
      const dx = (e.clientX - (r.left + r.width / 2)) / r.width;
      const dy = (e.clientY - (r.top + r.height / 2)) / r.height;
      btn.style.transform = `translate(${dx * 7}px, ${dy * 7 - 3}px) scale(1.06)`;
    };
    const reset = () => { btn.style.transform = ''; };
    btn.addEventListener('pointermove', onMove);
    btn.addEventListener('pointerleave', reset);
    btn.addEventListener('pointerdown', reset);
  }

  private get voiceEnabled(): boolean {
    return this.config.intelligence !== 'basic';
  }

  // ---- state-of-light machine ----
  private setState(s: AuraState): void {
    if (s === this.auraState) return;
    this.auraState = s;
    this.panel?.setAttribute('data-state', s);
    this.avatarAura?.setState(s);
    this.triggerAura?.setState(s);
    this.updateStatusText();
  }

  private updateStatusText(): void {
    const map: Record<AuraState, string> = {
      dormant: this.connText, listening: t('listening'), thinking: t('thinking'), speaking: t('speaking'),
    };
    if (this.statusEl?.lastChild) this.statusEl.lastChild.textContent = ' ' + map[this.auraState];
  }

  private markSpeaking(): void {
    this.speakingUntil = (typeof performance !== 'undefined' ? performance.now() : Date.now()) + 650;
  }

  /** One loop while the panel is open: feeds live amplitude to the reactive
   *  mic ring and resolves the current state-of-light from the session. */
  private startReactiveLoop(): void {
    if (typeof requestAnimationFrame !== 'function') return;
    const tick = () => {
      if (!this.open) { this.reactRaf = 0; return; }
      this.reactRaf = requestAnimationFrame(tick);
      const inL = this.session.inputLevel();
      const outL = this.session.outputLevel();
      this.style.setProperty('--fb-energy', Math.max(inL, outL).toFixed(3));
      const now = (typeof performance !== 'undefined' ? performance.now() : Date.now());
      if (outL > 0.04) this.markSpeaking();
      let next: AuraState;
      if (now < this.speakingUntil) next = 'speaking';      // she imparts — warm gold
      else if (this.thinking) next = 'thinking';            // she contemplates — bright shimmer
      else if (inL > 0.05) next = 'listening';              // you speak — cool silver
      else next = 'dormant';                                // present, at rest — warm gold
      this.setState(next);
    };
    this.reactRaf = requestAnimationFrame(tick);
  }

  // ---- UI helpers ----
  private addMessage(sender: 'user' | 'pragya' | 'system', text: string, grounding?: Grounding): void {
    const bubble = h('div', `bubble ${sender}`);
    const body = h('div');
    // Web links in the text become links (e.g. a recap, M2-6); the rest stays text.
    text.split(/(https?:\/\/[^\s<>"]+[^\s<>".,;:!?)])/).forEach((part, i) => {
      if (i % 2) {
        const a = h('a', undefined, part);
        a.href = part;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        body.append(a);
      } else body.append(part);
    });
    bubble.append(body);
    const sources = sourcesEl(grounding, (route) => this.hostBridge?.navigate(route));
    if (sources) bubble.append(sources);
    this.messagesEl.insertBefore(bubble, this.canvasEl);
    this.scrollDown();
  }

  private showThinking(): void {
    this.thinking = true;
    if (this.thinkingEl) return;
    const el = h('div', 'bubble pragya typing');
    el.append(h('span', 'dot'), h('span', 'dot'), h('span', 'dot'));
    el.setAttribute('aria-label', t('isThinking', { name: 'Pragya' }));
    this.thinkingEl = el;
    this.messagesEl.insertBefore(el, this.canvasEl);
    this.scrollDown();
  }

  private hideThinking(): void {
    this.thinking = false;
    if (!this.thinkingEl) return;
    this.thinkingEl.remove();
    this.thinkingEl = null;
  }

  private scrollDown(): void {
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }

  private submitText(text: string): void {
    if (!text.trim()) return;
    this.noteTalk();
    this.session.sendText(text.trim());
  }

  /** The visitor started talking: credit a trigger they clicked, stop nudging. */
  private noteTalk(): void {
    this.talked = true;
    this.shadowRoot?.querySelector('.fb-nudge')?.remove();
    this.triggers?.engaged();
  }

  private toggleVoice(): void {
    if (!this.session.active) this.noteTalk();
    if (this.session.active) {
      this.session.stopVoice();
      this.micBtn.classList.remove('live');
    } else {
      this.micBtn.classList.add('live');
      void this.session.startVoice().then(() => {
        if (!this.session.active) this.micBtn.classList.remove('live');
      });
    }
  }

  /** Snapshot of where the visitor is, sent to the backend for page-awareness. */
  private pageContext(): Record<string, unknown> {
    if (typeof location === 'undefined') return {};
    const page = location.pathname + (location.hash || '');
    const title = typeof document !== 'undefined' ? document.title : '';
    let section: string | undefined = location.hash ? location.hash.slice(1) : undefined;
    if (!section && typeof document !== 'undefined') {
      const heads = Array.from(document.querySelectorAll('h1,h2,h3')) as HTMLElement[];
      const vh = window.innerHeight || 800;
      const inView = heads.find((el) => {
        const r = el.getBoundingClientRect();
        return r.top >= -48 && r.top < vh * 0.6;
      });
      section = (inView?.textContent || '').trim().slice(0, 80) || undefined;
    }
    return { page, title, section, sections: this.pageSections() };
  }

  private pageSections(): Array<{ id: string; label: string }> {
    if (typeof document === 'undefined') return [];
    try {
      const out: Array<{ id: string; label: string }> = [];
      const seen = new Set<string>();
      for (const el of Array.from(document.querySelectorAll('[id]')) as HTMLElement[]) {
        const id = el.id;
        if (!id || seen.has(id)) continue;
        const tag = el.tagName.toLowerCase();
        const isSection =
          tag === 'section' ||
          (['div', 'main', 'article'].includes(tag) && !!el.querySelector('h1,h2,h3,h4'));
        if (!isSection) continue;
        const heading = el.querySelector('h1,h2,h3,h4');
        const label = (heading?.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 70);
        seen.add(id);
        out.push({ id, label });
        if (out.length >= 30) break;
      }
      return out;
    } catch {
      return [];
    }
  }

  // ---- public control surface (for host CTAs) ----
  // Each is a no-op until the UI exists: for a holdout visitor (WS11) it never
  // does, so a host's "Ask Pragya" button can't bring the agent back.
  ask(text: string): void {
    if (!this.shadowRoot) return;
    if (this.config.design === 'level1') this.openPanel();
    this.submitText(text);
  }

  // ---- open/close (Level 1 panel) ----
  toggle(): void {
    if (this.config.design !== 'level1') return;
    this.open ? this.close() : this.openPanel();
  }

  openPanel(): void {
    if (this.config.design !== 'level1' || !this.shadowRoot) return;
    this.open = true;
    this.trigger.classList.add('hidden');
    this.panel.classList.remove('hidden');
    if (this.voiceEnabled) this.session.primeAudio();
    this.session.connect();
    this.startReactiveLoop();
  }

  close(): void {
    if (!this.shadowRoot) return;
    this.open = false;
    this.session?.abortTour();
    if (this.reactRaf) { cancelAnimationFrame(this.reactRaf); this.reactRaf = 0; }
    this.panel.classList.add('hidden');
    this.trigger.classList.remove('hidden');
    this.setState('dormant');
  }
}
