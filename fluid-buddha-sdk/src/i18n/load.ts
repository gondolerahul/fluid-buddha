// Loads the Hindi table on demand. Bundlers split this dynamic import into its
// own chunk. The <script>-tag build swaps this module for load.global.ts.

import type { StringKey } from './index';

export function loadHindi(): Promise<Record<StringKey, string>> {
  return import('./hi').then((m) => m.hi);
}
