// Loads the Three.js particle field on demand (WS5): only Design Level 2 uses
// it, so Level 1 and Level 3 never download Three.js. Bundlers split this
// dynamic import into its own chunk. The <script>-tag build swaps this module
// for load.global.ts (see build.mjs).

import type { ParticleField } from './ParticleField';

export type ParticleFieldCtor = typeof ParticleField;

export function loadParticleField(): Promise<ParticleFieldCtor> {
  return import('./ParticleField').then((m) => m.ParticleField);
}
