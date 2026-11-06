// Loads the generated-regions controller on demand. Bundlers split this
// dynamic import into its own chunk. The <script>-tag build swaps this module
// for load.global.ts (see build.mjs).

import type { createController } from './controller';

export function loadRegions(): Promise<{ createController: typeof createController }> {
  return import('./controller');
}
