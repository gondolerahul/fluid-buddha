// Web Audio mic capture + lightweight energy VAD. Captures mic audio,
// downsamples to PCM16 @ 16 kHz mono, emits chunks, and detects speech
// start / endpoint so the client can open and close an utterance.

const TARGET_RATE = 16000;

export interface AudioCaptureHandlers {
  onChunk: (pcm16: Uint8Array) => void;
  onSpeechStart: () => void;
  onSpeechEnd: () => void;
}

export class AudioCapture {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private readonly handlers: AudioCaptureHandlers;

  private speaking = false;
  private silenceMs = 0;
  private voicedMs = 0;
  private lastLevel = 0;
  // Hysteresis + onset gating so the agent isn't interrupted by the slightest
  // sound (key clicks, breaths, room noise). A louder `startThreshold` must be
  // SUSTAINED for `attackMs` before we declare speech; once speaking, a gentler
  // `continueThreshold` keeps the utterance alive through natural dips, and only
  // `hangoverMs` of real silence ends it.
  private readonly startThreshold = 0.03;
  private readonly continueThreshold = 0.018;
  private readonly attackMs = 180;
  private readonly hangoverMs = 850;

  /** Smoothed 0..1 mic amplitude — lets views react to the user's voice. */
  level(): number {
    return this.lastLevel;
  }

  constructor(handlers: AudioCaptureHandlers) {
    this.handlers = handlers;
  }

  async start(): Promise<void> {
    // Echo cancellation keeps the agent's own TTS out of the mic so VAD only
    // triggers on the real user (clean barge-in, no self-interruption).
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    this.ctx = new AudioContext();
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.processor = this.ctx.createScriptProcessor(4096, 1, 1);

    const ratio = this.ctx.sampleRate / TARGET_RATE;
    this.processor.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0);
      this.runVad(input, e.inputBuffer.duration * 1000);
      this.handlers.onChunk(this.downsampleToPcm16(input, ratio));
    };

    this.source.connect(this.processor);
    this.processor.connect(this.ctx.destination);
  }

  private runVad(samples: Float32Array, frameMs: number): void {
    let sum = 0;
    for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
    const rms = Math.sqrt(sum / samples.length);
    // Normalise to ~0..1 and smooth for the particle energy feed.
    this.lastLevel += (Math.min(1, rms * 8) - this.lastLevel) * 0.4;

    if (!this.speaking) {
      // Onset: require energy SUSTAINED above the loud start threshold so a
      // single transient (click, cough, door) can't trigger a barge-in. Brief
      // dips leak the accumulator away rather than resetting it hard.
      if (rms > this.startThreshold) {
        this.voicedMs += frameMs;
        if (this.voicedMs >= this.attackMs) {
          this.voicedMs = 0;
          this.silenceMs = 0;
          this.speaking = true;
          this.handlers.onSpeechStart();
        }
      } else {
        this.voicedMs = Math.max(0, this.voicedMs - frameMs);
      }
      return;
    }

    // Speaking: stay open through natural pauses; only sustained real silence
    // (below the gentler continue threshold) closes the utterance.
    if (rms > this.continueThreshold) {
      this.silenceMs = 0;
    } else {
      this.silenceMs += frameMs;
      if (this.silenceMs >= this.hangoverMs) {
        this.speaking = false;
        this.silenceMs = 0;
        this.voicedMs = 0;
        this.handlers.onSpeechEnd();
      }
    }
  }

  private downsampleToPcm16(input: Float32Array, ratio: number): Uint8Array {
    const outLen = Math.floor(input.length / ratio);
    const out = new Int16Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const s = Math.max(-1, Math.min(1, input[Math.floor(i * ratio)]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return new Uint8Array(out.buffer);
  }

  stop(): void {
    this.processor?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.ctx?.close();
    this.ctx = null;
    this.stream = null;
    this.processor = null;
    this.source = null;
    this.speaking = false;
    this.silenceMs = 0;
    this.voicedMs = 0;
  }
}
