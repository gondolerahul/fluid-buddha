// Vanilla orchestrator (the framework-agnostic equivalent of the React
// useVoiceSession hook). Owns the WebSocket client, mic capture, jitter buffer
// and player; drives DOM commands through the HostBridge; surfaces UI updates
// through callbacks.

import { AudioCapture } from '../audio/AudioCapture';
import { AudioPlayer } from '../audio/AudioPlayer';
import { JitterBuffer } from '../audio/JitterBuffer';
import { ComponentPayload, Envelope, Grounding, PageSpec, Privacy, base64ToBytes } from '../protocol';
import { CONSENT_VERSION, hasConsent, rememberConsent } from '../ui/consent';
import { preloadComponents } from '../ui/components/canvas';
import type { ActionCard, ActionOutcome } from '../ui/actionCard';
import { ConnectionStatus, VoiceClient } from '../transport/VoiceClient';
import { FluidBuddhaConfig } from './config';
import { HostBridge } from './HostBridge';
import { LiveLink } from './Live';
import { TourController, TourStop } from './Tour';
import { getLang, t } from '../i18n';

export interface SessionCallbacks {
  onStatus: (s: ConnectionStatus) => void;
  onUserTranscript: (text: string, interim: boolean) => void;
  onAgentMessage: (text: string, grounding?: Grounding) => void;
  onComponent: (component: ComponentPayload) => void;
  onPatch: (targetSyncId: string, patch: Record<string, unknown>) => void;
  onSystem: (message: string) => void;
  /** A full runtime-generated page (Extreme intelligence). Optional. */
  onPage?: (page: PageSpec) => void;
  /** Fired as agent TTS audio streams in — lets a view react while speaking
   *  (e.g. Design Level 2 particle energy/colour). Optional. */
  onAgentAudio?: () => void;
  /** Short status from the guided tour (e.g. "touring"/""). Optional. */
  onTourStatus?: (text: string) => void;
  /** Ask the visitor to allow the microphone (WS8); resolve true to allow.
   *  Without it, a site that requires consent never starts the mic. */
  requestConsent?: (privacy: Privacy) => Promise<boolean>;
  /** A person from the site's team said something (live takeover, M2-2).
   *  Without it their messages show as agent messages, prefixed with their name. */
  onOperatorMessage?: (name: string, text: string) => void;
  /** A person wants to talk by voice; resolve true to accept. Without it calls
   *  are declined. */
  requestCall?: (name: string) => Promise<boolean>;
  /** A voice call with a person started (with a hang-up handle) or ended. */
  onCall?: (active: boolean, name: string, hangup: () => void) => void;
  /** The agent proposes an action (M2-8): show it; `answer(true)` confirms
   *  it (resolving with the outcome), `answer(false)` cancels. Without it
   *  proposals are ignored and nothing runs. */
  onProposal?: (card: ActionCard, answer: (confirm: boolean) => Promise<ActionOutcome | null>) => void;
}

// Used when the socket never says what the site wants: ask, to be safe.
const FALLBACK_PRIVACY: Privacy = { consent_required: true, retention_days: null, redacts_pii: true };

interface AnyRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult:
    | ((e: {
        resultIndex: number;
        results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>;
      }) => void)
    | null;
  onerror: (() => void) | null;
}

const RECAP_RE =
  /\b(send|email|mail|share|give) me (this|that|a (recap|summary|copy)|the (recap|summary|conversation))\b|\brecap (link|please)\b|रीकैप|(यह|ये|इसे|इसको)\s*(मुझे\s*)?(भेज|ईमेल)|\b(ye|yeh|ise|isko) (mujhe )?(bhej|email|mail)/i;

export class Session {
  private client: VoiceClient | null = null;
  private capture: AudioCapture | null = null;
  private player: AudioPlayer | null = null;
  private jitter: JitterBuffer | null = null;
  private recognition: AnyRecognition | null = null;
  /** The conversation's language (M2-7): the widget's to begin with, then
   *  what the server answers in. The browser's recogniser listens for it. */
  private talkLang = getLang();

  private lastTranscript = '';
  private pendingAudio = 0;
  private userSpeaking = false;
  private _active = false;
  private textSessionId: string | undefined;
  /** A person from the site's team, when they take over (M2-2). */
  private readonly live: LiveLink;
  /** The voice session's id (from `ready`), so a lead links to its conversation. */
  private wsSessionId: string | undefined;
  private greeted = false;
  private welcomeEnabled = false;
  private pageProvider?: () => Record<string, unknown>;
  private _audioUnlockArmed = false;
  private readonly tour: TourController;
  private tourDoneWaiters = new Map<number, () => void>();
  /** The site's privacy settings from `ready`, and callers waiting for them. */
  private privacy: Privacy | null = null;
  private readySeen = false;
  private privacyWaiters: Array<() => void> = [];
  /** After an in-app route change (D-15) the agent needs the new page. */
  private readonly onNavigated = () => this.reportCurrentPage();

  constructor(
    private readonly config: FluidBuddhaConfig,
    private readonly bridge: HostBridge,
    private readonly cb: SessionCallbacks,
  ) {
    this.live = new LiveLink({
      notice: (text) => this.cb.onSystem(text),
      message: (name, text) =>
        this.cb.onOperatorMessage ? this.cb.onOperatorMessage(name, text) : this.cb.onAgentMessage(`${name}: ${text}`),
      requestCall: this.cb.requestCall,
      onCall: this.cb.onCall,
      signal: (type, payload) => this.client?.sendRaw('EVENTS', type, payload),
      quietAgent: (stopMic) => {
        this.jitter?.reset();
        this.abortTour();
        if (stopMic && this._active) this.stopVoice();
      },
    });
    // The tour drives speak→scroll choreography through this thin host adapter;
    // narration is requested over the socket and gated on playback completion.
    this.tour = new TourController({
      say: (text, index) => this.client?.sendRaw('EVENTS', 'tour_say', { text, index }),
      awaitSaid: (index) => this.awaitTourDone(index),
      isSpeaking: () => this.jitter?.isPlaying() ?? false,
      navigate: (route) => this.bridge.navigate(route),
      scroll: (target) => this.tourScroll(target),
      currentPath: () => (typeof location !== 'undefined' ? location.pathname : ''),
      status: (text) => this.cb.onTourStatus?.(text),
    });
    if (typeof window !== 'undefined')
      window.addEventListener('fluidbuddha:navigated', this.onNavigated);
  }

  get active(): boolean {
    return this._active;
  }

  /** Live 0..1 mic amplitude (user speaking) — 0 when not capturing. */
  inputLevel(): number {
    return this.capture?.level() ?? 0;
  }

  /** Live 0..1 amplitude of the agent's TTS as it actually plays out loud. */
  outputLevel(): number {
    return this.player?.level() ?? 0;
  }

  private wsUrl(): string {
    const base = (this.config.backend || 'ws://localhost:8080').replace(/\/$/, '');
    const q = new URLSearchParams({
      site: this.config.site,
      intelligence: this.config.intelligence,
      design: this.config.design,
      // Audio as binary frames, not base64 JSON (WS5); an older server
      // ignores this and `ready` says which one it speaks.
      audio: 'binary',
    });
    // The widget key is what authorises a customer site; the backend resolves
    // the site and tier from it.
    if (this.config.key) q.set('key', this.config.key);
    return `${base}/ws/voice?${q.toString()}`;
  }

  /** Merge the configured capability levels into a context payload so the
   *  backend gates tools per-turn even if the query params were dropped by a
   *  proxy. */
  private withLevels(ctx: Record<string, unknown>): Record<string, unknown> {
    return {
      ...ctx,
      intelligence: this.config.intelligence,
      design: this.config.design,
      tour: this.config.tour,
    };
  }

  connect(): void {
    if (this.client?.isOpen) return;
    // A conversation is starting: fetch the diagram renderers now so the
    // first one shows without a wait (basic/high never draw components).
    if (this.config.intelligence === 'advance' || this.config.intelligence === 'extreme') {
      preloadComponents().catch(() => undefined);
    }
    if (!this.client) {
      this.client = new VoiceClient(this.wsUrl(), {
        onEnvelope: (env) => this.feed(env),
        onStatus: (s) => {
          this.cb.onStatus(s);
          if (s === 'failed') this.cb.onSystem(t('voiceUnavailable'));
        },
      });
    }
    this.client.connect();
  }

  /** Feed a server envelope into the session (used by the transport + tests). */
  feed(env: Envelope): void {
    const sid = env.sync_id || '';
    switch (env.channel) {
      case 'EVENTS':
        if (this.live.handle(env.type, env.payload)) break;
        if (env.type === 'ready') {
          if (typeof env.payload.session_id === 'string') this.wsSessionId = env.payload.session_id;
          if (env.payload.privacy) this.privacy = env.payload.privacy as Privacy;
          this.readySeen = true;
          this.privacyWaiters.splice(0).forEach((w) => w());
          const cfg =
            (env.payload.config as {
              filler_delay_ms?: number;
              sample_rate?: number;
              audio_frames?: string;
            }) || {};
          if (this.client) this.client.binaryAudio = cfg.audio_frames === 'binary';
          // Reuse a player primed during the open gesture (so welcome audio is
          // allowed to autoplay); otherwise create it now.
          if (!this.player) this.player = new AudioPlayer(cfg.sample_rate ?? 24000);
          if (!this.jitter) this.jitter = new JitterBuffer(this.player, cfg.filler_delay_ms ?? 1500);
          this.player.resume();
          this.onReady();
        } else if (env.type === 'navigate') {
          this.bridge.navigate(String(env.payload.path || ''));
        } else if (env.type === 'scroll_to') {
          this.bridge.scrollTo({
            sectionId: env.payload.sectionId ? String(env.payload.sectionId) : undefined,
            direction: env.payload.direction ? String(env.payload.direction) : undefined,
          });
        } else if (env.type === 'set_persona') {
          this.bridge.setPersona(String(env.payload.persona || ''));
        } else if (env.type === 'action_proposal') {
          this.propose(env.payload as unknown as ActionCard);
        } else if (env.type === 'language') {
          this.setTalkLang(env.payload.lang);
        } else if (env.type === 'tour_plan') {
          const stops = (env.payload.stops as TourStop[]) || [];
          if (this.config.tour && stops.length) void this.tour.run(stops);
        } else if (env.type === 'tour_done') {
          this.resolveTourDone(Number(env.payload.index ?? -1));
        } else if (env.type === 'recalibrating') {
          this.cb.onSystem(t('recalibrating'));
        } else if (env.type === 'interrupted') {
          this.jitter?.reset();
          this.tour.abort(); // a real barge-in ends the tour
        } else if (env.type === 'consent_required') {
          // Audio reached a server session that hasn't heard the consent yet.
          if (hasConsent(this.consentKey)) this.sendConsent();
        } else if (env.type === 'error') {
          this.cb.onSystem(String(env.payload.message || t('error')));
        }
        break;
      case 'STATE':
        if (env.type === 'transcript') this.cb.onUserTranscript(String(env.payload.text || ''), false);
        break;
      case 'DATA':
        if (env.type === 'render') this.cb.onComponent(env.payload as unknown as ComponentPayload);
        else if (env.type === 'render_page')
          this.cb.onPage?.(env.payload as unknown as PageSpec);
        else if (env.type === 'patch')
          this.cb.onPatch(
            String(env.payload.target_sync_id || ''),
            (env.payload.patch as Record<string, unknown>) || {},
          );
        break;
      case 'AUDIO':
        if (env.type === 'start') {
          this.pendingAudio += 1;
          this.jitter?.startAudio(sid, sid.startsWith('ui_'));
          const text = String(env.payload.text || '');
          if (text && !sid.startsWith('ack_'))
            this.cb.onAgentMessage(text, env.payload.grounding as Grounding | undefined);
        } else if (env.type === 'chunk') {
          // Binary frames arrive as raw `pcm`; JSON ones as base64 `data`.
          const raw = env.payload.pcm;
          const data = env.payload.data as string | undefined;
          const pcm = raw instanceof Uint8Array ? raw : data ? base64ToBytes(data) : null;
          if (pcm) {
            this.jitter?.pushAudio(sid, pcm);
            if (!sid.startsWith('ack_')) this.cb.onAgentAudio?.();
          }
        } else if (env.type === 'end') {
          this.pendingAudio = Math.max(0, this.pendingAudio - 1);
          this.jitter?.endAudio(sid);
        }
        break;
    }
  }

  // ---- voice ----
  private startRecognition(): void {
    const w = window as unknown as {
      SpeechRecognition?: new () => AnyRecognition;
      webkitSpeechRecognition?: new () => AnyRecognition;
    };
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) return;
    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = this.speechLang;
    rec.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        const t = r[0].transcript;
        if (r.isFinal) this.lastTranscript = t;
        else interim += t;
      }
      if (interim) this.cb.onUserTranscript(interim, true);
    };
    rec.onerror = () => {
      /* VAD + server ASR still work */
    };
    this.recognition = rec;
    try {
      rec.start();
    } catch {
      /* already started */
    }
  }

  private get speechLang(): string {
    return this.talkLang === 'hi' ? 'hi-IN' : 'en-IN';
  }

  private setTalkLang(lang: unknown): void {
    if ((lang !== 'en' && lang !== 'hi') || lang === this.talkLang) return;
    this.talkLang = lang;
    if (this.recognition) this.recognition.lang = this.speechLang; // used from its next start
  }

  private get consentKey(): string {
    return this.config.key || this.config.site;
  }

  private sendConsent(): void {
    this.client?.sendRaw('EVENTS', 'consent', { mic: true, version: CONSENT_VERSION });
  }

  /** Resolves with the site's privacy settings once the socket is ready. */
  private awaitPrivacy(timeoutMs = 4000): Promise<Privacy> {
    if (this.readySeen) return Promise.resolve(this.privacy ?? FALLBACK_PRIVACY);
    return new Promise((resolve) => {
      const t = setTimeout(() => resolve(this.privacy ?? FALLBACK_PRIVACY), timeoutMs);
      this.privacyWaiters.push(() => {
        clearTimeout(t);
        resolve(this.privacy ?? FALLBACK_PRIVACY);
      });
    });
  }

  /** Microphone consent (WS8): ask once per site, remember the answer in this
   *  browser, and tell the server before any audio is sent. */
  private async ensureMicConsent(): Promise<boolean> {
    const privacy = await this.awaitPrivacy();
    if (!privacy.consent_required) return true;
    if (!hasConsent(this.consentKey)) {
      const ok = (await this.cb.requestConsent?.(privacy)) ?? false;
      if (!ok) return false;
      rememberConsent(this.consentKey);
    }
    this.sendConsent();
    return true;
  }

  async startVoice(): Promise<void> {
    this.connect();
    this.player?.resume();
    this.reportCurrentPage();
    if (!(await this.ensureMicConsent())) {
      this._active = false;
      this.cb.onSystem(t('voiceOff'));
      return;
    }
    this.startRecognition();
    const capture = new AudioCapture({
      onChunk: (pcm) => {
        if (this.userSpeaking) this.client?.sendAudioChunk(pcm);
      },
      onSpeechStart: () => {
        // Barge-in must key off ACTUAL playback, not the network in-flight
        // counter: the server bursts the whole utterance, so `pendingAudio`
        // returns to 0 long before the audio finishes playing. Using only that
        // counter meant the agent ignored interruptions mid-answer.
        if (this.jitter?.isPlaying() || this.pendingAudio > 0) {
          this.client?.sendBargeIn();
          this.jitter?.reset();
          this.pendingAudio = 0;
          this.abortTour(); // speaking over the tour ends it
        }
        this.lastTranscript = '';
        this.userSpeaking = true;
        this.client?.startAudio();
      },
      onSpeechEnd: () => {
        this.userSpeaking = false;
        const t = this.lastTranscript.trim();
        this.client?.endAudio(t || undefined);
        this.lastTranscript = '';
      },
    });
    try {
      await capture.start();
      this.capture = capture;
      this._active = true;
    } catch {
      this.cb.onSystem(t('micUnavailable'));
      this._active = false;
    }
  }

  stopVoice(): void {
    this.abortTour();
    this.capture?.stop();
    this.capture = null;
    try {
      this.recognition?.stop();
    } catch {
      /* noop */
    }
    this.recognition = null;
    this.jitter?.reset();
    this._active = false;
  }

  // ---- text ----
  sendText(text: string): void {
    if (!text.trim()) return;
    // "Send me this" / "email me a recap at me@x.com" (M2-6): a shareable
    // recap of the conversation instead of a turn.
    if (this.config.key && RECAP_RE.test(text)) {
      this.cb.onUserTranscript(text, false);
      void this.recap(text.match(/[\w.+-]+@[\w-]+(\.[\w-]+)+/)?.[0]);
      return;
    }
    this.abortTour(); // a typed question takes over from the tour
    this.connect();
    if (this.client?.isOpen) {
      this.reportCurrentPage(); // keep the agent location-aware for this turn
      this.client.sendText(text); // server echoes the user transcript + answer
    } else {
      void this.httpFallback(text);
    }
  }

  /** Show a proposed action; the visitor's answer goes to the server (M2-8). */
  private propose(card: ActionCard): void {
    if (!card || !card.id || !this.cb.onProposal) return;
    this.cb.onProposal(card, async (yes) => {
      try {
        const res = await fetch(`${(this.config.api || '').replace(/\/$/, '')}/actions/${yes ? 'confirm' : 'cancel'}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key: this.config.key, site: this.config.site,
            session_id: this.wsSessionId ?? this.textSessionId, run_id: card.id }),
        });
        const d = await res.json();
        return res.ok ? (d as ActionOutcome) : { status: 'failed', error: String(d.detail || '') || null };
      } catch {
        return null;
      }
    });
  }

  /** Build (or refresh) this conversation's recap link, optionally emailed. */
  async recap(email?: string): Promise<void> {
    const say = (t: string) => this.cb.onAgentMessage(t);
    try {
      const res = await fetch(`${(this.config.api || '').replace(/\/$/, '')}/recap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: this.config.key, site: this.config.site,
          session_id: this.wsSessionId ?? this.textSessionId, email }),
      });
      if (res.status === 404 || res.status === 422) {
        say(t(res.status === 404 ? 'recapFirst' : 'recapBadEmail'));
        return;
      }
      const d = await res.json();
      if (!res.ok || !d.url) throw new Error();
      say(t('recapReady', { url: d.url }) + (d.emailed ? t('recapEmailed', { email: email || '' }) : ''));
    } catch {
      say(t('recapFailed'));
    }
  }

  /** Store an enquiry-form submission as a lead (WS7). Posts straight to the
   *  backend — the visitor's details never pass through the LLM. */
  async submitLead(values: Record<string, string>): Promise<boolean> {
    try {
      const res = await fetch(`${(this.config.api || '').replace(/\/$/, '')}/leads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: this.config.key || undefined,
          site: this.config.site,
          session_id: this.wsSessionId ?? this.textSessionId,
          values,
        }),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  private async httpFallback(text: string): Promise<void> {
    this.cb.onUserTranscript(text, false);
    try {
      const ctx = (this.pageProvider?.() ?? {}) as { page?: string; sections?: unknown };
      const res = await fetch(`${(this.config.api || '').replace(/\/$/, '')}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_id: this.textSessionId,
          key: this.config.key || undefined,
          site: this.config.site,
          intelligence: this.config.intelligence,
          design: this.config.design,
          exp: this.config.exp,
          lang: getLang(),
          page: ctx.page ?? (typeof location !== 'undefined' ? location.pathname : undefined),
          sections: ctx.sections,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        this.cb.onSystem(t('offline'));
        return;
      }
      this.textSessionId = data.session_id ?? this.textSessionId;
      this.setTalkLang(data.lang);
      ((data.proposals as ActionCard[] | undefined) || []).forEach((c) => this.propose(c));
      if (data.takeover) {
        // A person has the chat: their replies come from /chat/live (M2-2).
        const base = (this.config.api || '').replace(/\/$/, '');
        const q = new URLSearchParams({ session_id: String(this.textSessionId || '') });
        if (this.config.key) q.set('key', this.config.key);
        else if (this.config.site) q.set('site', this.config.site);
        void this.live.poll(`${base}/chat/live?${q}`, Number(data.takeover.after || 0));
        return;
      }
      this.cb.onAgentMessage(data.text || '…', data.grounding);
      (data.actions || []).forEach(
        (a: { type: string; path?: string; icp?: string; sectionId?: string; direction?: string }) => {
          if (a.type === 'navigate' && a.path) this.bridge.navigate(a.path);
          else if (a.type === 'set_icp' && a.icp) this.bridge.setPersona(a.icp);
          else if (a.type === 'scroll_to' && (a.sectionId || a.direction))
            this.bridge.scrollTo({ sectionId: a.sectionId, direction: a.direction });
        },
      );
      (data.components || []).forEach((c: ComponentPayload) => this.cb.onComponent(c));
      (data.pages || []).forEach((p: PageSpec) => this.cb.onPage?.(p));
    } catch {
      this.cb.onSystem(t('connError'));
    }
  }

  notifyRendered(syncId: string): void {
    this.jitter?.markRendered(syncId);
  }

  // ---- guided tour helpers ----
  /** Resolves when the server has finished sending tour stop `index`'s audio. */
  private awaitTourDone(index: number): Promise<void> {
    return new Promise((resolve) => this.tourDoneWaiters.set(index, resolve));
  }
  private resolveTourDone(index: number): void {
    const r = this.tourDoneWaiters.get(index);
    if (r) {
      this.tourDoneWaiters.delete(index);
      r();
    }
  }
  private tourScroll(target: string): void {
    if (['down', 'up', 'top', 'bottom'].includes(target)) this.bridge.scrollTo({ direction: target });
    else this.bridge.scrollTo({ sectionId: target });
  }
  /** Stop the guided tour (close, new user turn, or barge-in). */
  abortTour(): void {
    this.tour.abort();
    this.tourDoneWaiters.forEach((r) => r());
    this.tourDoneWaiters.clear();
  }

  reportState(payload: Record<string, unknown>): void {
    this.client?.sendState(payload);
  }

  /** Forward a component's interactive state (the visitor played with a slider,
   *  expanded a node, switched a tab…) so the agent can react. Safe no-op when
   *  the socket is closed. */
  reportComponentState(syncId: string, patch: Record<string, unknown>): void {
    this.reportState({ component_state: { sync_id: syncId, ...patch } });
  }

  /** The agent was opened by a proactive trigger whose message is its opener
   *  (M2-3): don't also play the welcome or start the tour. */
  skipWelcome(): void {
    this.greeted = true;
  }

  /** Supply the current-page context and opt into a spoken welcome on open. */
  enableWelcome(provider: () => Record<string, unknown>): void {
    this.pageProvider = provider;
    this.welcomeEnabled = true;
  }

  /** Create + resume the AudioContext synchronously inside a user gesture so the
   *  welcome audio is permitted to autoplay once the socket is ready. */
  primeAudio(): void {
    if (!this.player) this.player = new AudioPlayer(24000);
    if (!this.jitter) this.jitter = new JitterBuffer(this.player, 1500);
    this.player.resume();
    this.armAudioUnlock();
  }

  /** Autoplay fallback: if audio is still suspended (no user gesture yet, e.g.
   *  autoStart on a cold load), resume it on the first interaction anywhere so
   *  the already-queued welcome starts playing immediately. */
  private armAudioUnlock(): void {
    if (this._audioUnlockArmed || typeof window === 'undefined') return;
    this._audioUnlockArmed = true;
    const unlock = () => {
      this.player?.resume();
      window.removeEventListener('pointerdown', unlock);
      window.removeEventListener('keydown', unlock);
      window.removeEventListener('touchstart', unlock);
      this._audioUnlockArmed = false;
    };
    window.addEventListener('pointerdown', unlock);
    window.addEventListener('keydown', unlock);
    window.addEventListener('touchstart', unlock);
  }

  /** Push the visitor's current page/section so the agent is location-aware. */
  reportCurrentPage(): void {
    const ctx = this.pageProvider?.();
    if (ctx && this.client?.isOpen) this.client.sendState(this.withLevels(ctx));
  }

  /** Called once the socket is ready: report location, then greet if enabled. */
  private onReady(): void {
    this.reportCurrentPage();
    // A reconnect is a new server session: repeat a consent already given.
    if (this._active && hasConsent(this.consentKey)) this.sendConsent();
    if (this.welcomeEnabled && !this.greeted) {
      this.greeted = true;
      // The test variant goes with the hello: the server speaks its greeting
      // and starts in its persona (M2-4).
      this.client?.sendHello({ ...this.withLevels(this.pageProvider?.() ?? {}), exp: this.config.exp,
        lang: getLang() });
    }
  }

  destroy(): void {
    if (typeof window !== 'undefined')
      window.removeEventListener('fluidbuddha:navigated', this.onNavigated);
    this.stopVoice();
    this.client?.close();
    this.client = null;
  }
}
