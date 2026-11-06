// Loads the plan patcher on demand (a split chunk for bundlers; the
// <script>-tag build swaps in load.global.ts, see build.mjs).

import type { applyPatch, PageRenderer } from './patcher';

export function loadPatcher(): Promise<{ applyPatch: typeof applyPatch; PageRenderer: typeof PageRenderer }> {
  return import('./patcher');
}
