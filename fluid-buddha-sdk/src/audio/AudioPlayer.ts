// Plays PCM16 TTS segments through Web Audio. Each "segment" is the full audio
// for one sync_id; the JitterBuffer decides *when* a segment may play.

export class AudioPlayer {
  private ctx: AudioContext | null = null;
  private current: AudioBufferSourceNode | null = null;
  private readonly sampleRate: number;
  // Output tap so views can react to the ACTUAL spoken waveform (Design Level 2
  // particle energy syncs to speech, not to network chunk timing).
  private out: GainNode | null = null;
  private analyser: AnalyserNode | null = null;
  private levelData: Uint8Array<ArrayBuffer> | null = null;
  private smoothLevel = 0;

  constructor(sampleRate = 24000) {
    this.sampleRate = sampleRate;
  }

  private ensureCtx(): AudioContext {
    if (!this.ctx) {
      const Ctor =
        (globalThis as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext })
          .AudioContext ||
        (globalThis as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) throw new Error('AudioContext unavailable');
      this.ctx = new Ctor({ sampleRate: this.sampleRate });
      // source → gain → analyser → speakers; analyser taps the live signal.
      this.out = this.ctx.createGain();
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 256;
      this.out.connect(this.analyser);
      this.analyser.connect(this.ctx.destination);
      this.levelData = new Uint8Array(new ArrayBuffer(this.analyser.fftSize));
    }
    return this.ctx;
  }

  /** Smoothed 0..1 amplitude of what is currently playing (RMS of the output). */
  level(): number {
    if (!this.analyser || !this.levelData) return 0;
    this.analyser.getByteTimeDomainData(this.levelData);
    let sum = 0;
    for (let i = 0; i < this.levelData.length; i++) {
      const v = (this.levelData[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / this.levelData.length);
    const lvl = Math.min(1, rms * 3.4);
    this.smoothLevel += (lvl - this.smoothLevel) * 0.35;
    return this.smoothLevel;
  }

  play(chunks: Uint8Array[]): Promise<void> {
    const ctx = this.ensureCtx();
    const total = chunks.reduce((n, c) => n + c.byteLength, 0);
    if (total === 0) return Promise.resolve();

    const pcm = new Uint8Array(total);
    let off = 0;
    for (const c of chunks) {
      pcm.set(c, off);
      off += c.byteLength;
    }
    const view = new DataView(pcm.buffer);
    const frames = pcm.byteLength / 2;
    const buffer = ctx.createBuffer(1, frames, this.sampleRate);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < frames; i++) channel[i] = view.getInt16(i * 2, true) / 0x8000;

    return new Promise((resolve) => {
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.connect(this.out ?? ctx.destination);
      src.onended = () => {
        if (this.current === src) this.current = null;
        resolve();
      };
      this.current = src;
      src.start();
    });
  }

  playFiller(durationMs = 450): Promise<void> {
    const ctx = this.ensureCtx();
    const frames = Math.floor((this.sampleRate * durationMs) / 1000);
    const buffer = ctx.createBuffer(1, frames, this.sampleRate);
    const ch = buffer.getChannelData(0);
    for (let i = 0; i < frames; i++) {
      const fade = Math.min(1, i / 400, (frames - i) / 400);
      ch[i] = Math.sin((2 * Math.PI * 220 * i) / this.sampleRate) * 0.04 * fade;
    }
    return new Promise((resolve) => {
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.connect(this.out ?? ctx.destination);
      src.onended = () => resolve();
      src.start();
    });
  }

  stop(): void {
    try {
      this.current?.stop();
    } catch {
      /* already stopped */
    }
    this.current = null;
  }

  /** True while a TTS segment is actually being played out loud. */
  isPlaying(): boolean {
    return this.current !== null;
  }

  resume(): void {
    try {
      void this.ensureCtx().resume();
    } catch {
      /* no AudioContext (SSR / test env) — playback simply won't engage */
    }
  }
}
