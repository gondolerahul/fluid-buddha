// Guided Website Tour playback (Req 5).
//
// The plan is authored at ingestion (backend) and arrives as a list of stops.
// Each stop is: speak the narration → wait until the agent has FINISHED speaking
// → only THEN perform the stop's move (scroll within the page, or navigate to
// another page) → next stop. Gating every move on speech completion is what
// makes the explain/scroll sync feel right rather than "off".
//
// The controller is transport-agnostic: it drives a small `TourHost` the Session
// implements (request narration, know when speech is done, navigate, scroll).

export interface TourMove {
  type: 'navigate' | 'scroll';
  route?: string;
  target?: string; // for scroll: 'down' | 'up' | 'top' | 'bottom' | a section id
}

export interface TourStop {
  narration: string;
  move?: TourMove;
  label?: string;
}

export interface TourHost {
  /** Ask the agent to speak this narration (server synthesizes + streams it). */
  say(text: string, index: number): void;
  /** Resolves once the server has sent ALL of this narration's audio (so once
   *  playback then drains, the narration is truly finished). */
  awaitSaid(index: number): Promise<void>;
  /** True while TTS audio is still buffered or playing. */
  isSpeaking(): boolean;
  navigate(route: string): void;
  scroll(target: string): void;
  /** Current page path, so we only navigate when the target page differs. */
  currentPath(): string;
  /** Surface a short status string (e.g. "touring") — optional. */
  status?(text: string): void;
}

const delay = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));

export class TourController {
  private aborted = false;
  private running = false;

  constructor(private readonly host: TourHost) {}

  get active(): boolean {
    return this.running;
  }

  /** Stop the tour (barge-in, close, or a new user turn). Idempotent. */
  abort(): void {
    if (!this.running) return;
    this.aborted = true;
  }

  async run(stops: TourStop[]): Promise<void> {
    if (this.running || !stops || stops.length === 0) return;
    this.running = true;
    this.aborted = false;
    this.host.status?.('touring');
    try {
      for (let i = 0; i < stops.length; i++) {
        if (this.aborted) break;
        const stop = stops[i];
        if (stop.narration) await this.speakStop(stop.narration, i);
        if (this.aborted) break;
        await this.performMove(stop.move);
        if (this.aborted) break;
        await delay(450); // a beat between stops
      }
    } finally {
      this.running = false;
      this.host.status?.('');
    }
  }

  private async speakStop(text: string, index: number): Promise<void> {
    this.host.say(text, index);
    // 1) Wait until the server reports it has sent the whole narration. The
    //    20s cap is a safety net if a tour_done is ever lost.
    await Promise.race([this.host.awaitSaid(index), delay(20000)]);
    if (this.aborted) return;
    // 2) Then wait until playback drains. Because (1) guarantees no more audio
    //    is inbound, the first moment we're not speaking IS the end of the
    //    narration — no risk of firing the move during an inter-sentence gap.
    await this.waitUntil(() => !this.host.isSpeaking(), 90000);
  }

  private async performMove(move?: TourMove): Promise<void> {
    if (!move || this.aborted) return;
    if (move.type === 'navigate' && move.route) {
      if (move.route !== this.host.currentPath()) {
        this.host.navigate(move.route);
        await delay(950); // let the SPA route render before the next narration
      }
    } else if (move.type === 'scroll' && move.target) {
      this.host.scroll(move.target);
      await delay(750); // let the smooth scroll settle
    }
  }

  private async waitUntil(pred: () => boolean, timeoutMs: number): Promise<void> {
    const start = Date.now();
    while (!this.aborted && !pred() && Date.now() - start < timeoutMs) {
      await delay(120);
    }
  }
}
