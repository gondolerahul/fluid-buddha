// <script>-tag build of load.ts: an IIFE can't split chunks, so the particle
// field ships as its own file, fluid-buddha-particles.global.js, next to
// fluid-buddha.global.js, and is fetched only when Design Level 2 starts.

import type { ParticleField } from './ParticleField';

export type ParticleFieldCtor = typeof ParticleField;

export const PARTICLES_FILE = 'fluid-buddha-particles.global.js';

type ParticlesGlobal = { ParticleField: ParticleFieldCtor };

// Resolved while this script runs, when currentScript still points at it.
const baseUrl = ((): string => {
  if (typeof document === 'undefined') return '';
  const own = document.currentScript as HTMLScriptElement | null;
  const src =
    own?.src ||
    document.querySelector<HTMLScriptElement>('script[src*="fluid-buddha"][src$=".global.js"]')?.src ||
    '';
  return src;
})();

let pending: Promise<ParticleFieldCtor> | null = null;

export function loadParticleField(): Promise<ParticleFieldCtor> {
  const w = window as unknown as { FluidBuddhaParticles?: ParticlesGlobal };
  if (w.FluidBuddhaParticles) return Promise.resolve(w.FluidBuddhaParticles.ParticleField);
  if (pending) return pending;
  pending = new Promise<ParticleFieldCtor>((resolve, reject) => {
    if (!baseUrl) {
      reject(new Error('fluid-buddha: cannot locate the particles bundle'));
      return;
    }
    const s = document.createElement('script');
    s.src = new URL(PARTICLES_FILE, baseUrl).href;
    s.async = true;
    s.onload = () =>
      w.FluidBuddhaParticles
        ? resolve(w.FluidBuddhaParticles.ParticleField)
        : reject(new Error('fluid-buddha: particles bundle did not register'));
    s.onerror = () => reject(new Error(`fluid-buddha: failed to load ${s.src}`));
    document.head.appendChild(s);
  }).catch((err) => {
    pending = null; // allow a retry on the next open
    throw err;
  });
  return pending;
}
