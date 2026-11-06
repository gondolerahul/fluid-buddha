"use client";
/**
 * The console's side of a voice call with a visitor (M2-2): a WebRTC audio
 * call signalled through the backend. The operator makes the offer; the
 * visitor's widget asks them to accept and answers; ICE candidates flow both
 * ways; relay (TURN) servers come from the backend with short-lived
 * credentials.
 */
import { Api } from "./api";

export class OperatorCall {
  private pc: RTCPeerConnection | null = null;
  private stream: MediaStream | null = null;
  private audio: HTMLAudioElement | null = null;
  private pendingIce: RTCIceCandidateInit[] = [];
  private ended = false;

  constructor(readonly websiteId: string, readonly sessionId: string,
              private readonly onEnd: (why: string) => void,
              private readonly onConnected: () => void) {}

  async start(): Promise<void> {
    const { ice_servers } = await Api.liveIce();
    const pc = new RTCPeerConnection({ iceServers: ice_servers });
    this.pc = pc;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    this.stream.getTracks().forEach((t) => pc.addTrack(t, this.stream as MediaStream));
    pc.onicecandidate = (e) => {
      if (e.candidate) void Api.callSignal(this.websiteId, this.sessionId,
        { type: "ice", candidate: e.candidate.toJSON() }).catch(() => {});
    };
    pc.ontrack = (e) => {
      if (!this.audio) {
        this.audio = new Audio();
        this.audio.autoplay = true;
      }
      this.audio.srcObject = e.streams[0];
      void this.audio.play().catch(() => {});
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "connected") this.onConnected();
      if (pc.connectionState === "failed") this.hangup(true, "The call couldn't connect.");
    };
    const offer = await pc.createOffer({ offerToReceiveAudio: true });
    await pc.setLocalDescription(offer);
    await Api.callSignal(this.websiteId, this.sessionId, { type: "offer", sdp: offer.sdp });
  }

  async answered(sdp: string): Promise<void> {
    if (!this.pc) return;
    await this.pc.setRemoteDescription({ type: "answer", sdp });
    for (const c of this.pendingIce.splice(0)) await this.pc.addIceCandidate(c).catch(() => {});
  }

  async ice(candidate: RTCIceCandidateInit): Promise<void> {
    if (!this.pc?.remoteDescription) {
      this.pendingIce.push(candidate);
      return;
    }
    await this.pc.addIceCandidate(candidate).catch(() => {});
  }

  hangup(notify: boolean, why = "Call ended."): void {
    if (this.ended) return;
    this.ended = true;
    if (notify) void Api.callSignal(this.websiteId, this.sessionId, { type: "hangup" }).catch(() => {});
    this.pc?.close();
    this.pc = null;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    if (this.audio) this.audio.srcObject = null;
    this.onEnd(why);
  }
}
