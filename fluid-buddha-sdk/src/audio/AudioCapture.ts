// Web Audio mic capture. Captures mic audio off the main thread with an
// AudioWorklet (falling back to the deprecated ScriptProcessorNode where
// worklets are unavailable or blocked by CSP), and hands each frame to the
// SpeechGate, which detects speech start / endpoint and emits PCM16 @ 16 kHz
// mono — including a short pre-roll so the first word isn't clipped.

import { SpeechGate, SpeechGateHandlers } from './SpeechGate';

export type AudioCaptureHandlers = SpeechGateHandlers;

// ~20 ms frames at 48 kHz: fine-grained enough for a responsive VAD, coarse
// enough to keep main-thread messages cheap.
const WORKLET_FRAME = 1024;

// Inline worklet (loaded from a Blob URL, so there is no second file to host).
// It batches the 128-sample render quanta into WORKLET_FRAME-sample frames.
const WORKLET_SOURCE = `
class FluidBuddhaCapture extends AudioWorkletProcessor {
  constructor() { super(); this.buf = new Float32Array(${WORKLET_FRAME}); this.n = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) {
      let i = 0;
      while (i < ch.length) {
        const take = Math.min(ch.length - i, this.buf.length - this.n);
        this.buf.set(ch.subarray(i, i + take), this.n);
        this.n += take; i += take;
        if (this.n === this.buf.length) {
          this.port.postMessage(this.buf, [this.buf.buffer]);
          this.buf = new Float32Array(${WORKLET_FRAME}); this.n = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor('fluid-buddha-capture', FluidBuddhaCapture);
`;

export class AudioCapture {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private node: AudioWorkletNode | ScriptProcessorNode | null = null;
  private readonly gate: SpeechGate;

  constructor(handlers: AudioCaptureHandlers) {
    this.gate = new SpeechGate(handlers);
  }

  /** Smoothed 0..1 mic amplitude — lets views react to the user's voice. */
  level(): number {
    return this.gate.level();
  }

  async start(): Promise<void> {
    // Echo cancellation keeps the agent's own TTS out of the mic so VAD only
    // triggers on the real user (clean barge-in, no self-interruption).
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    this.ctx = new AudioContext();
    this.source = this.ctx.createMediaStreamSource(this.stream);
    const rate = this.ctx.sampleRate;
    this.node = (await this.workletNode(this.ctx, rate)) ?? this.scriptNode(this.ctx, rate);
    this.source.connect(this.node);
    // Outputs silence; connecting keeps the node pulled by the audio graph.
    this.node.connect(this.ctx.destination);
  }

  private async workletNode(ctx: AudioContext, rate: number): Promise<AudioWorkletNode | null> {
    if (!ctx.audioWorklet || typeof AudioWorkletNode === 'undefined') return null;
    let url = '';
    try {
      url = URL.createObjectURL(new Blob([WORKLET_SOURCE], { type: 'application/javascript' }));
      await ctx.audioWorklet.addModule(url);
      const node = new AudioWorkletNode(ctx, 'fluid-buddha-capture', {
        numberOfInputs: 1,
        numberOfOutputs: 1,
        channelCount: 1,
      });
      node.port.onmessage = (e: MessageEvent<Float32Array>) => this.gate.process(e.data, rate);
      return node;
    } catch {
      return null; // e.g. a CSP without blob: in worker-src / script-src
    } finally {
      if (url) URL.revokeObjectURL(url);
    }
  }

  private scriptNode(ctx: AudioContext, rate: number): ScriptProcessorNode {
    const node = ctx.createScriptProcessor(2048, 1, 1);
    node.onaudioprocess = (e) => this.gate.process(e.inputBuffer.getChannelData(0), rate);
    return node;
  }

  stop(): void {
    const node = this.node;
    if (node && 'port' in node) node.port.onmessage = null;
    else if (node) node.onaudioprocess = null;
    node?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.ctx?.close();
    this.ctx = null;
    this.stream = null;
    this.node = null;
    this.source = null;
    this.gate.reset();
  }
}
