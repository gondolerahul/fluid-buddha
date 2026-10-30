// Shared incremental-reveal helper. Paints a component "piece by piece" in sync
// with the spoken explanation (Req 3.5.2) by staggering CSS animation delays,
// and reports progress so Design Level 2 can move the particle system at the
// activity midpoint (req vi). Generalizes the staggering originally inlined in
// flowchart.ts so every renderer animates consistently.

const schedule: (cb: () => void, ms: number) => void =
  typeof setTimeout === 'function' ? (cb, ms) => void setTimeout(cb, ms) : (cb) => cb();

export interface RevealOptions {
  /** ms between successive items (default 350). */
  stepMs?: number;
  /** initial offset before the first item appears (default 0). */
  startMs?: number;
  /** fired as each item becomes visible, with the 1-based count and total. */
  onProgress?: (revealed: number, total: number) => void;
  /** fired once when roughly half the items have been revealed. */
  onMidpoint?: () => void;
}

/** Stagger the appearance of `items` (DOM or SVG elements). Each gets the
 *  `fb-reveal-item` class + an animation-delay; progress/midpoint callbacks fire
 *  on matching timers (so they work even where animation events don't). */
export function revealSequence(
  items: Array<HTMLElement | SVGElement>,
  opts: RevealOptions = {},
): void {
  const step = opts.stepMs ?? 350;
  const start = opts.startMs ?? 0;
  const total = items.length;
  if (total === 0) {
    opts.onMidpoint?.();
    return;
  }
  const midIdx = Math.floor((total - 1) / 2);
  items.forEach((el, i) => {
    el.classList.add('fb-reveal-item');
    (el as HTMLElement).style.animationDelay = `${(start + i * step) / 1000}s`;
    schedule(() => {
      opts.onProgress?.(i + 1, total);
      if (i === midIdx) opts.onMidpoint?.();
    }, start + i * step);
  });
}

/** Total time (ms) a reveal of `count` items takes — handy for timing a
 *  follow-up action (e.g. the particle move-back) without per-item callbacks. */
export function revealDuration(count: number, stepMs = 350): number {
  return Math.max(0, count) * stepMs;
}
