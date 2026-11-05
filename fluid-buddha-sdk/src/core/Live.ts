// Live takeover (M2-2): a person from the site's team joins the conversation.
//
// Over the voice socket the server pushes `operator_joined`, `operator_message`,
// `operator_left` and the call signals; in text mode (no socket) the widget
// long-polls `/chat/live` for the person's replies while they have the chat.
//
// A voice call is plain WebRTC between the visitor's browser and the person's
// console, signalled through our server; the visitor must accept, the agent's
// microphone pipeline is off for the call, and the relay (TURN) servers come
// with the offer.

import { t } from '../i18n';

export interface LiveCallbacks {
  notice: (text: string) => void;
  message: (name: string, text: string) => void;
  /** Ask the visitor to accept a call; resolve true to accept. */
  requestCall?: (name: string) => Promise<boolean>;
  /** A call started (with a way to hang up) or ended. */
  onCall?: (active: boolean, name: string, hangup: () => void) => void;
  /** Send a signal to the server (voice socket). */
  signal: (type: string, payload: Record<string, unknown>) => void;
  /** Stop the agent's speech (and, for a call, its microphone) while a person talks. */
  quietAgent: (stopMic: boolean) => void;
}

type IceServer = { urls: string | string[]; username?: string; credential?: string };

export class LiveLink {
  operator: string | null = null;
  private pc: RTCPeerConnection | null = null;
  private stream: MediaStream | null = null;
  private audio: HTMLAudioElement | null = null;
  private pendingIce: RTCIceCandidateInit[] = [];
  private polling = false;

  constructor(private readonly cb: LiveCallbacks) {}

  /** Handle a server EVENTS envelope; true when it was a live event. */
  handle(type: string, p: Record<string, unknown>): boolean {
    const name = String(p.name || this.operator || t('someoneTeam'));
    switch (type) {
      case 'operator_joined':
        this.operator = name;
        this.cb.quietAgent(false);
        this.cb.notice(t('joined', { name }));
        return true;
      case 'operator_message':
        this.cb.message(name, String(p.text || ''));
        return true;
      case 'operator_left':
        this.operator = null;
        this.endCall(false);
        this.cb.notice(t('handedBack', { name }));
        return true;
      case 'call_offer':
        void this.onOffer(name, String(p.sdp || ''), (p.ice_servers as IceServer[]) || []);
        return true;
      case 'call_ice':
        if (p.candidate) void this.addIce(p.candidate as RTCIceCandidateInit);
        return true;
      case 'call_hangup':
        if (this.pc) this.cb.notice(t('endedCall', { name }));
        this.endCall(false);
        return true;
    }
    return false;
  }

  private async onOffer(name: string, sdp: string, iceServers: IceServer[]): Promise<void> {
    const RTC = (globalThis as { RTCPeerConnection?: typeof RTCPeerConnection }).RTCPeerConnection;
    const media = typeof navigator !== 'undefined' ? navigator.mediaDevices : undefined;
    if (!RTC || !media?.getUserMedia || this.pc) {
      this.cb.signal('call_decline', { reason: this.pc ? 'busy' : 'unsupported' });
      return;
    }
    const ok = (await this.cb.requestCall?.(name)) ?? false;
    if (!ok) {
      this.cb.signal('call_decline', {});
      return;
    }
    try {
      this.cb.quietAgent(true);
      const pc = new RTC({ iceServers });
      this.pc = pc;
      this.stream = await media.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      this.stream.getTracks().forEach((t) => pc.addTrack(t, this.stream as MediaStream));
      pc.onicecandidate = (e) => {
        if (e.candidate) this.cb.signal('call_ice', { candidate: e.candidate.toJSON() });
      };
      pc.ontrack = (e) => {
        if (!this.audio) {
          this.audio = new Audio();
          this.audio.autoplay = true;
        }
        this.audio.srcObject = e.streams[0];
        void this.audio.play().catch(() => undefined);
      };
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === 'failed') {
          this.cb.notice(t('callFailed'));
          this.hangup();
        }
      };
      await pc.setRemoteDescription({ type: 'offer', sdp });
      for (const c of this.pendingIce.splice(0)) await pc.addIceCandidate(c);
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      this.cb.signal('call_answer', { sdp: answer.sdp });
      this.cb.onCall?.(true, name, () => this.hangup());
    } catch {
      this.cb.notice(t('micForCall'));
      this.cb.signal('call_decline', { reason: 'no_microphone' });
      this.endCall(false);
    }
  }

  private async addIce(c: RTCIceCandidateInit): Promise<void> {
    if (!this.pc || !this.pc.remoteDescription) {
      this.pendingIce.push(c);
      return;
    }
    try {
      await this.pc.addIceCandidate(c);
    } catch {
      /* a stale candidate */
    }
  }

  hangup(): void {
    if (this.pc) this.cb.signal('call_hangup', {});
    this.endCall(true);
  }

  private endCall(local: boolean): void {
    const was = !!this.pc;
    this.pc?.close();
    this.pc = null;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    if (this.audio) this.audio.srcObject = null;
    this.pendingIce = [];
    if (was) this.cb.onCall?.(false, this.operator || '', () => undefined);
    void local;
  }

  /** Text mode: fetch the person's replies until they hand back. */
  async poll(url: string, after: number): Promise<void> {
    if (this.polling) return;
    this.polling = true;
    let last = after;
    try {
      for (let i = 0; i < 500; i++) {
        const res = await fetch(`${url}&after=${last}`);
        if (!res.ok) break;
        const data = (await res.json()) as {
          messages: { id: number; sender: string; author: string | null; text: string }[];
          takeover: { name: string } | null;
        };
        for (const m of data.messages) {
          last = Math.max(last, m.id);
          if (m.sender === 'operator') this.cb.message(m.author || t('team'), m.text);
          else if (m.sender === 'system') this.cb.notice(m.text);
        }
        this.operator = data.takeover?.name ?? null;
        if (!data.takeover) break;
      }
    } catch {
      /* offline: the next message retries */
    } finally {
      this.polling = false;
    }
  }
}
