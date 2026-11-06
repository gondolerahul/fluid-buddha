// <script>-tag build of load.ts: an IIFE can't split chunks, so the particle
// field ships as its own file, fluid-buddha-particles.global.js, next to
// fluid-buddha.global.js, and is fetched only when Design Level 2 starts.

import type { ParticleField } from './ParticleField';
import { loadGlobal } from '../scriptLoader';

export type ParticleFieldCtor = typeof ParticleField;

export const PARTICLES_FILE = 'fluid-buddha-particles.global.js';

export function loadParticleField(): Promise<ParticleFieldCtor> {
  return loadGlobal<{ ParticleField: ParticleFieldCtor }>(PARTICLES_FILE, 'FluidBuddhaParticles').then(
    (m) => m.ParticleField,
  );
}
