// Generative UI canvas (arch §4.1). Maps DATA component payloads to safe,
// pre-built renderers — the LLM never emits raw HTML. After a card paints it
// calls onRendered(sync_id) so the jitter buffer can release the synced audio.
//
// The renderers load on demand (bodies.ts): until they arrive a card shows its
// caption and a placeholder, and onRendered waits for the real drawing.

import { ComponentPayload } from '../../protocol';
import type { BuildBody } from './bodies';
import { RenderContext } from './interactive';
import { loadBodies } from './load';

const nextFrame: (cb: () => void) => void =
  typeof requestAnimationFrame === 'function'
    ? (cb) => requestAnimationFrame(cb)
    : (cb) => setTimeout(cb, 0);

let bodies: BuildBody | undefined;
let loading: Promise<BuildBody> | undefined;

/** Hand the renderers over directly (the recap bundle already has them). */
export function provideBodies(b: BuildBody): void {
  bodies = b;
}

/** Fetch the renderers now (a conversation started), so the first diagram
 *  doesn't wait for them. Safe to call often. */
export function preloadComponents(): Promise<BuildBody> {
  if (bodies) return Promise.resolve(bodies);
  loading =
    loading ||
    loadBodies().then(
      (b) => (bodies = b),
      (err) => {
        loading = undefined; // retry on the next card
        throw err;
      },
    );
  return loading;
}

export class Canvas {
  private cards = new Map<string, { card: HTMLElement; payload: ComponentPayload }>();

  constructor(
    private readonly container: HTMLElement,
    private readonly onRendered: (syncId: string) => void,
    /** Optional: receive a component's interactive state when the user plays
     *  with it (forwarded to the agent). */
    private readonly onState?: (syncId: string, patch: Record<string, unknown>) => void,
  ) {}

  /** The card, and a promise that settles once its body is drawn. */
  private buildCard(payload: ComponentPayload, patch?: Record<string, unknown>): [HTMLElement, Promise<void>] {
    const card = document.createElement('div');
    card.className = 'card';
    if (payload.explanation_text) {
      const cap = document.createElement('div');
      cap.className = 'caption';
      cap.textContent = payload.explanation_text;
      card.appendChild(cap);
    }
    const ctx: RenderContext = {
      syncId: payload.sync_id,
      reportState: this.onState ? (p) => this.onState!(payload.sync_id, p) : undefined,
    };
    const draw = (b: BuildBody) => {
      card.querySelector('.card-wait')?.remove();
      card.appendChild(b(payload, patch, ctx));
    };
    if (bodies) {
      draw(bodies);
      return [card, Promise.resolve()];
    }
    const wait = document.createElement('div');
    wait.className = 'card-wait empty';
    card.appendChild(wait);
    return [card, preloadComponents().then(draw, () => undefined)];
  }

  add(payload: ComponentPayload): void {
    if (this.cards.has(payload.sync_id)) return;
    const [card, drawn] = this.buildCard(payload);
    this.container.appendChild(card);
    this.cards.set(payload.sync_id, { card, payload });
    // A failed load still releases the synced speech.
    drawn.then(() => nextFrame(() => this.onRendered(payload.sync_id)));
  }

  applyPatch(syncId: string, patch: Record<string, unknown>): void {
    const entry = this.cards.get(syncId);
    if (!entry) return;
    const [replacement] = this.buildCard(entry.payload, patch);
    entry.card.replaceWith(replacement);
    this.cards.set(syncId, { card: replacement, payload: entry.payload });
  }

  clear(): void {
    this.container.replaceChildren();
    this.cards.clear();
  }
}
