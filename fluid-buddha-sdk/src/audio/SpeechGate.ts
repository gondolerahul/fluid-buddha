// Energy VAD + pre-roll for mic capture. Fed raw mic frames at the capture
// rate; emits PCM16 @ 16 kHz mono only while the visitor is speaking, and opens
// each utterance with the audio from just BEFORE speech was detected.
//
// Speech is only declared after `attackMs` of sustained energy, so without a
// pre-roll the first ~180 ms of every utterance (often the first word) never
// reached the server ASR. The gate keeps a short ring of recent audio and
// flushes it when speech starts.

const TARGET_RATE = 16000;

export interface SpeechGateHandlers {
  onChunk: (pcm16: Uint8Array) => void;
  onSpeechStart: () => void;
  onSpeechEnd: () => void;
}

export interface SpeechGateOptions {
  /** Audio kept from before speech is detected. Covers the attack window
   *  plus a little lead-in. Default 400 ms. */
  prerollMs?: number;
}

export class SpeechGate {
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

  private readonly prerollMs: number;
  private preroll: Array<{ pcm: Uint8Array; ms: number }> = [];
  private prerollTotal = 0;
  // Resampler state carried between frames (the unfinished window's samples
  // and the fractional position in it), so a non-integer ratio (44.1 kHz)
  // doesn't drift or click at frame edges.
  private carry = new Float32Array(0);
  private readPos = 0;

  constructor(
    private readonly handlers: SpeechGateHandlers,
    opts: SpeechGateOptions = {},
  ) {
    this.prerollMs = opts.prerollMs ?? 400;
  }

  /** Smoothed 0..1 mic amplitude — lets views react to the user's voice. */
  level(): number {
    return this.lastLevel;
  }

  get isSpeaking(): boolean {
    return this.speaking;
  }

  /** Feed one frame of mono mic samples captured at `sampleRate`. */
  process(samples: Float32Array, sampleRate: number): void {
    if (!samples.length) return;
    const frameMs = (samples.length / sampleRate) * 1000;
    const pcm = this.downsample(samples, sampleRate / TARGET_RATE);
    const wasSpeaking = this.speaking;
    this.runVad(samples, frameMs);

    if (!wasSpeaking && this.speaking) {
      // Utterance opened: send what came just before it, then this frame.
      this.preroll.forEach((p) => this.handlers.onChunk(p.pcm));
      this.preroll = [];
      this.prerollTotal = 0;
      this.handlers.onChunk(pcm);
    } else if (this.speaking) {
      this.handlers.onChunk(pcm);
    } else {
      this.remember(pcm, frameMs);
    }
  }

  reset(): void {
    this.speaking = false;
    this.silenceMs = 0;
    this.voicedMs = 0;
    this.lastLevel = 0;
    this.preroll = [];
    this.prerollTotal = 0;
    this.carry = new Float32Array(0);
    this.readPos = 0;
  }

  private remember(pcm: Uint8Array, ms: number): void {
    this.preroll.push({ pcm, ms });
    this.prerollTotal += ms;
    while (this.preroll.length > 1 && this.prerollTotal - this.preroll[0].ms >= this.prerollMs) {
      this.prerollTotal -= this.preroll.shift()!.ms;
    }
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

  /** Resample to 16 kHz PCM16, averaging each output sample's input window
   *  (a cheap low-pass, so decimation doesn't alias). */
  private downsample(input: Float32Array, ratio: number): Uint8Array {
    if (ratio <= 1) {
      const out = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) out[i] = toInt16(input[i]);
      return new Uint8Array(out.buffer);
    }
    let buf = input;
    if (this.carry.length) {
      buf = new Float32Array(this.carry.length + input.length);
      buf.set(this.carry);
      buf.set(input, this.carry.length);
    }
    const values: number[] = [];
    let pos = this.readPos;
    while (pos + ratio <= buf.length) {
      const start = Math.floor(pos);
      const end = Math.floor(pos + ratio);
      let acc = 0;
      for (let i = start; i < end; i++) acc += buf[i];
      values.push(acc / Math.max(1, end - start));
      pos += ratio;
    }
    // Keep the samples of the unfinished window for the next frame.
    const consumed = Math.floor(pos);
    this.carry = buf.slice(consumed);
    this.readPos = pos - consumed;
    const out = new Int16Array(values.length);
    for (let i = 0; i < values.length; i++) out[i] = toInt16(values[i]);
    return new Uint8Array(out.buffer);
  }
}

function toInt16(s: number): number {
  const c = Math.max(-1, Math.min(1, s));
  return c < 0 ? c * 0x8000 : c * 0x7fff;
}
