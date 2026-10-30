// DOM Mutator & Persona Switcher (arch §4.2) — host-agnostic.
//
// Every command both (a) dispatches a `fluidbuddha:*` CustomEvent on window so
// any host can react, and (b) applies a sensible default. Provide a hook to
// fully take over (e.g. drive a SPA router or a Redux/setICP persona switch).

import { FluidBuddhaHooks } from './config';

export class HostBridge {
  constructor(private readonly hooks: FluidBuddhaHooks) {}

  private emit(name: string, detail: Record<string, unknown>): void {
    try {
      window.dispatchEvent(new CustomEvent(`fluidbuddha:${name}`, { detail }));
    } catch {
      /* non-DOM env */
    }
  }

  navigate(path: string): void {
    if (!path) return;
    this.emit('navigate', { path });
    if (this.hooks.onNavigate) {
      this.hooks.onNavigate(path);
      return;
    }
    try {
      window.location.assign(path);
    } catch {
      /* ignore */
    }
  }

  scrollTo(target: { sectionId?: string; direction?: string }): void {
    const sectionId = target.sectionId?.trim();
    const direction = target.direction?.trim();
    if (!sectionId && !direction) return;
    this.emit('scroll_to', { sectionId, direction });
    if (this.hooks.onScrollTo) {
      this.hooks.onScrollTo(target);
      return;
    }
    if (direction) {
      this.scrollDirection(direction);
      return;
    }
    if (sectionId) this.scrollToSection(sectionId);
  }

  /** Relative scrolling: "down a bit" / "up" / "top" / "bottom". */
  private scrollDirection(dir: string): void {
    try {
      const vh = window.innerHeight || 600;
      const max = document.documentElement.scrollHeight;
      if (dir === 'top') window.scrollTo({ top: 0, behavior: 'smooth' });
      else if (dir === 'bottom') window.scrollTo({ top: max, behavior: 'smooth' });
      else if (dir === 'up') window.scrollBy({ top: -vh * 0.85, behavior: 'smooth' });
      else window.scrollBy({ top: vh * 0.85, behavior: 'smooth' }); // down
    } catch {
      /* non-DOM env */
    }
  }

  /** Resolve a section by id, then by id-substring, then by heading text — the
   *  agent names sections loosely ("testimonials") and pages rarely have a
   *  matching DOM id, so fall back to fuzzy matching instead of doing nothing. */
  private scrollToSection(raw: string): void {
    const id = raw.replace(/^#/, '');
    let el: Element | null = null;
    try {
      el = document.getElementById(id);
    } catch {
      /* ignore */
    }
    if (!el) el = this.findByText(id);
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  private findByText(query: string): Element | null {
    const needle = query.replace(/[-_]/g, ' ').toLowerCase().trim();
    if (!needle) return null;
    try {
      const byId = Array.from(document.querySelectorAll('[id]')).find((el) =>
        el.id.replace(/[-_]/g, ' ').toLowerCase().includes(needle),
      );
      if (byId) return byId;
      const heads = Array.from(document.querySelectorAll('h1,h2,h3,h4'));
      return (
        heads.find((el) => (el.textContent || '').toLowerCase().includes(needle)) || null
      );
    } catch {
      return null;
    }
  }

  setPersona(persona: string): void {
    if (!persona) return;
    this.emit('set_persona', { persona });
    const apply = () => {
      if (this.hooks.onSetPersona) {
        this.hooks.onSetPersona(persona);
        return;
      }
      // Default: expose persona as an attribute the host's CSS/JS can key off.
      try {
        document.documentElement.setAttribute('data-fb-persona', persona);
      } catch {
        /* ignore */
      }
    };
    this.crossfade(apply);
  }

  /** Premium 300ms cross-fade (Req 3.6.3): mask the host persona swap behind a
   *  brief translucent veil so the DOM never flashes mid-change. Falls back to
   *  an instant switch when motion is reduced or there's no DOM. */
  private crossfade(apply: () => void): void {
    const reduce =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || typeof document === 'undefined' || !document.body) {
      apply();
      return;
    }
    try {
      const veil = document.createElement('div');
      veil.setAttribute('data-fb-persona-veil', '');
      veil.style.cssText = [
        'position:fixed',
        'inset:0',
        'z-index:2147483646',
        'pointer-events:none',
        'opacity:0',
        'background:radial-gradient(120% 120% at 50% 0%, rgba(22,19,14,0.42), rgba(8,8,10,0.28))',
        'backdrop-filter:blur(2px)',
        '-webkit-backdrop-filter:blur(2px)',
        'transition:opacity 150ms ease',
        'will-change:opacity',
      ].join(';');
      document.body.appendChild(veil);
      requestAnimationFrame(() => {
        veil.style.opacity = '1';
      });
      // Swap at peak opacity, then fade the veil out and remove it.
      window.setTimeout(() => {
        apply();
        veil.style.opacity = '0';
        window.setTimeout(() => veil.remove(), 200);
      }, 150);
    } catch {
      apply();
    }
  }
}
