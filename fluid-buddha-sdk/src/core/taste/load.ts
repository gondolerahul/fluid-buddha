// Loads the preferences panel on demand (a split chunk for bundlers; the
// <script>-tag build swaps in load.global.ts, see build.mjs).

import type { openPanel } from './panel';

export function loadPanel(): Promise<{ openPanel: typeof openPanel }> {
  return import('./panel');
}
