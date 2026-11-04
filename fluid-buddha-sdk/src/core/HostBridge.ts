// DOM Mutator & Persona Switcher (arch §4.2) — host-agnostic.
//
// Every command both (a) dispatches a `fluidbuddha:*` CustomEvent on window so
// any host can react, and (b) applies a sensible default. Provide a hook to
// fully take over (e.g. drive a SPA router or a Redux/setICP persona switch).
//
// Navigation (D-15) never hard-reloads a single-page app by default. The
// `fluidbuddha:navigate` event is cancelable — call `preventDefault()` to route
// it yourself — or pass `hooks.onNavigate`. Otherwise, in `auto` mode, the
// bridge pushes the route onto history and fires `popstate`, which the common
// routers (React Router, Vue Router, Next.js, SvelteKit…) answer by rendering
// the page. If nothing on the page changes, it is a multi-page site, so the
// bridge falls back to a normal page load.

import { FluidBuddhaHooks, NavigationMode } from './config';

/** How long `auto` navigation waits for a router to render before it falls
 *  back to a full page load. */
export const SPA_RENDER_WAIT_MS = 600;

export class HostBridge {
  constructor(
    private readonly hooks: FluidBuddhaHooks,
    private readonly navigation: NavigationMode = 'auto',
  ) {}

  /** Dispatch `fluidbuddha:<name>`; false when a listener cancelled it. */
  private emit(name: string, detail: Record<string, unknown>, cancelable = false): boolean {
    try {
      return window.dispatchEvent(new CustomEvent(`fluidbuddha:${name}`, { detail, cancelable }));
    } catch {
      return true; /* non-DOM env */
    }
  }

  navigate(path: string): void {
    if (!path) return;
    const proceed = this.emit('navigate', { path }, true);
    if (this.hooks.onNavigate) {
      this.hooks.onNavigate(path);
      return;
    }
    if (!proceed) return; // the host routed it
    let url: URL;
    try {
      url = new URL(path, window.location.href);
    } catch {
      return;
    }
    const here = window.location;
    if (url.origin !== here.origin || this.navigation === 'reload') {
      this.hardNavigate(url.href);
      return;
    }
    if (url.pathname === here.pathname && url.search === here.search) {
      // Same page: at most a jump to an anchor.
      if (url.hash && url.hash !== here.hash) this.scrollTo({ sectionId: url.hash });
      return;
    }
    this.softNavigate(url);
  }

  private hardNavigate(href: string): void {
    try {
      window.location.assign(href);
    } catch {
      /* ignore */
    }
  }

  /** Route without a reload: pushState + popstate. In `auto` mode, fall back
   *  to a page load when no router answered by changing the page. */
  private softNavigate(url: URL): void {
    const href = url.pathname + url.search + url.hash;
    let rendered = this.navigation === 'spa';
    let observer: MutationObserver | null = null;
    let timer = 0;
    let settled = false;
    const settle = () => {
      if (settled) return;
      settled = true;
      observer?.disconnect();
      window.clearTimeout(timer);
      if (rendered) this.emit('navigated', { path: href, mode: 'spa' });
      // Nothing re-rendered: a multi-page site. Load the page for real.
      else if (window.location.pathname === url.pathname) this.hardNavigate(url.href);
    };
    if (!rendered && typeof window.MutationObserver !== 'undefined' && document.body) {
      observer = new window.MutationObserver((records) => {
        if (records.some(isPageChange)) {
          rendered = true;
          settle(); // the router answered: no need to wait out the timer
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
    try {
      window.history.pushState({ fluidbuddha: true }, '', href);
      window.dispatchEvent(new window.PopStateEvent('popstate', { state: window.history.state }));
    } catch {
      settled = true;
      observer?.disconnect();
      this.hardNavigate(url.href);
      return;
    }
    if (rendered) settle();
    else timer = window.setTimeout(settle, SPA_RENDER_WAIT_MS);
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

/** A DOM change made by the host page (a router rendering), not by the
 *  widget itself or its persona veil. */
function isPageChange(r: MutationRecord): boolean {
  const nodes = [...Array.from(r.addedNodes), ...Array.from(r.removedNodes)];
  return nodes.some((n) => {
    if (n.nodeType !== 1) return false; // text-only churn (tickers, clocks)
    const el = n as Element;
    return el.localName !== 'fluid-buddha' && !el.hasAttribute('data-fb-persona-veil');
  });
}
