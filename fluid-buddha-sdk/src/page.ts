// The hosted campaign page's script (M3-1), dist/fluid-buddha-page.global.js.
//
// The page is server-rendered and complete without it. This only:
// - draws the interactive sections (ROI calculator, charts) into their slots
//   from the JSON block <script type="application/json" id="fb-page-data">;
// - reports engagement once, to the URL in this script's data-events, when
//   the visitor scrolls past half the page, uses a component or the agent,
//   or stays 15 seconds with the page visible. Same-origin, no identifiers
//   beyond the page's own first-party cookie.

import { renderSlots } from './slots';

export function renderPage(doc: Document = document): number {
  return renderSlots(doc, 'fb-page-data', 'page');
}

export function watchEngagement(doc: Document, url: string, win: Window = window,
                                visibleMs = 15000): () => void {
  let sent = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const send = () => {
    if (sent) return;
    sent = true;
    stop();
    const body = JSON.stringify({ kind: 'engage' });
    try {
      const nav = win.navigator as Navigator & { sendBeacon?: (u: string, d: Blob) => boolean };
      if (nav.sendBeacon && nav.sendBeacon(url, new Blob([body], { type: 'text/plain' }))) return;
    } catch {
      /* fall back to fetch */
    }
    void win.fetch(url, { method: 'POST', body, headers: { 'Content-Type': 'text/plain' },
                          credentials: 'same-origin', keepalive: true }).catch(() => undefined);
  };
  const onScroll = () => {
    const el = doc.documentElement;
    const seen = (win.scrollY + win.innerHeight) / Math.max(el.scrollHeight, 1);
    if (seen > 0.5 && el.scrollHeight > win.innerHeight * 1.2) send();
  };
  const onUse = (e: Event) => {
    const t = e.target as HTMLElement | null;
    if (t && (t.closest?.('[data-fb-slot]') || t.closest?.('fluid-buddha') || t.tagName === 'FLUID-BUDDHA')) send();
  };
  const arm = () => {
    if (timer) clearTimeout(timer);
    timer = doc.visibilityState === 'hidden' ? undefined : setTimeout(send, visibleMs);
  };
  const stop = () => {
    if (timer) clearTimeout(timer);
    win.removeEventListener('scroll', onScroll);
    doc.removeEventListener('pointerdown', onUse, true);
    doc.removeEventListener('input', onUse, true);
    doc.removeEventListener('visibilitychange', arm);
  };
  win.addEventListener('scroll', onScroll, { passive: true });
  doc.addEventListener('pointerdown', onUse, true);
  doc.addEventListener('input', onUse, true);
  doc.addEventListener('visibilitychange', arm);
  arm();
  return stop;
}

if (typeof document !== 'undefined') {
  const me = document.currentScript as HTMLScriptElement | null;
  const events = me?.getAttribute('data-events') || '';
  const start = () => {
    renderPage();
    if (events) watchEngagement(document, events);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
}
