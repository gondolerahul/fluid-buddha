// Loads the component renderers on demand. Bundlers split this dynamic import
// into its own chunk. The <script>-tag build swaps this module for
// load.global.ts (see build.mjs).

import type { BuildBody } from './bodies';

export function loadBodies(): Promise<BuildBody> {
  return import('./bodies').then((m) => m.buildBody);
}
