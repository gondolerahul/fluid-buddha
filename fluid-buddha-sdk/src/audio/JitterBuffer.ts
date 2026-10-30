// Multimodal sync engine. Holds incoming TTS audio per sync_id and only
// releases a component-linked segment AFTER its UI has rendered. If rendering
// exceeds the filler delay it plays a short filler tone first. Segments play in
// arrival (FIFO) order; barge-in clears everything.

import { AudioPlayer } from './AudioPlayer';

interface Segment {
  chunks: Uint8Array[];
  gated: boolean;
  rendered: boolean;
}

export class JitterBuffer {
  private readonly player: AudioPlayer;
  private readonly fillerDelayMs: number;
  private segments = new Map<string, Segment>();
  private ready: string[] = [];
  private renderResolvers = new Map<string, () => void>();
  private running = false;
  private generation = 0;

  constructor(player: AudioPlayer, fillerDelayMs = 1500) {
    this.player = player;
    this.fillerDelayMs = fillerDelayMs;
  }

  startAudio(syncId: string, gated: boolean): void {
    this.segments.set(syncId, { chunks: [], gated, rendered: false });
  }

  pushAudio(syncId: string, bytes: Uint8Array): void {
    const seg = this.segments.get(syncId) ?? { chunks: [], gated: false, rendered: false };
    seg.chunks.push(bytes);
    this.segments.set(syncId, seg);
  }

  endAudio(syncId: string): void {
    if (!this.segments.has(syncId)) return;
    this.ready.push(syncId);
    void this.pump();
  }

  markRendered(syncId: string): void {
    const seg = this.segments.get(syncId);
    if (seg) seg.rendered = true;
    this.renderResolvers.get(syncId)?.();
    this.renderResolvers.delete(syncId);
  }

  reset(): void {
    this.generation += 1;
    this.ready = [];
    this.segments.clear();
    this.renderResolvers.forEach((r) => r());
    this.renderResolvers.clear();
    this.player.stop();
    this.running = false;
  }

  /** True while audio is playing OR queued to play — the correct signal for
   *  barge-in (unlike a network in-flight counter, which empties early). */
  isPlaying(): boolean {
    return (
      this.running ||
      this.ready.length > 0 ||
      this.segments.size > 0 ||
      this.player.isPlaying()
    );
  }

  private waitForRender(syncId: string): Promise<void> {
    return new Promise((resolve) => this.renderResolvers.set(syncId, resolve));
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private async pump(): Promise<void> {
    if (this.running) return;
    this.running = true;
    const gen = this.generation;

    while (this.ready.length && gen === this.generation) {
      const id = this.ready.shift()!;
      const seg = this.segments.get(id);
      if (!seg) continue;

      if (seg.gated && !seg.rendered) {
        await Promise.race([this.waitForRender(id), this.delay(this.fillerDelayMs)]);
        if (gen !== this.generation) break;
        if (!seg.rendered) await this.player.playFiller();
      }
      if (gen !== this.generation) break;
      await this.player.play(seg.chunks);
      this.segments.delete(id);
    }
    if (gen === this.generation) this.running = false;
  }
}
