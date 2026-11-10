// The visitor's preferences panel (Phase 3), loaded on demand.
//
// Shows each preference with its current value and whether the visitor chose
// it or it was inferred; changes are explicit choices. "Reset" clears them all;
// "Forget me" also removes a remembered profile (POST /memory remember:false).

import { getTaste, setTaste, TasteConfig, TasteRaw } from '../taste';
import { visitorId } from '../Experiment';

const LABELS: Record<string, string> = {
  density: 'Layout', format: 'Format', detail: 'Detail', modality: 'How you use the agent', tone: 'Tone',
  motion: 'Motion', scheme: 'Colour scheme',
};
const OPTIONS: Record<string, string[]> = {
  density: ['airy', 'balanced', 'compact'], format: ['prose', 'bullets', 'tables', 'charts', 'visuals'],
  detail: ['summary', 'standard', 'deep'], modality: ['voice', 'text', 'silent'],
  tone: ['formal', 'friendly', 'concise'], motion: ['calm', 'standard', 'lively'], scheme: ['light', 'dark', 'auto'],
};

const CSS = `
:host{all:initial}
.bg{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:2147483646;display:flex;align-items:center;justify-content:center;font:14px/1.5 ui-sans-serif,system-ui,sans-serif}
.box{background:#14161c;color:#f3f5f7;border-radius:16px;padding:22px;width:min(420px,92vw);max-height:86vh;overflow:auto;box-shadow:0 20px 60px rgba(0,0,0,.5)}
h2{margin:0 0 4px;font-size:18px} p{margin:0 0 14px;color:#9aa3b2;font-size:13px}
.row{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:8px 0}
.row small{display:block;color:#9aa3b2;font-size:11px}
select{background:#0c0b09;color:inherit;border:1px solid #333;border-radius:8px;padding:6px 8px;font:inherit}
.btns{display:flex;gap:8px;justify-content:flex-end;margin-top:16px;flex-wrap:wrap}
button{font:inherit;border-radius:10px;border:1px solid #333;background:transparent;color:inherit;padding:8px 12px;cursor:pointer}
button.primary{background:#c9a24a;color:#0c0b09;border-color:#c9a24a}`;

async function send(cfg: TasteConfig, events: unknown[]): Promise<TasteRaw | null> {
  try {
    const res = await fetch(`${cfg.api.replace(/\/$/, '')}/experience/taste`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: cfg.key || undefined, visitor: visitorId() || undefined, taste: getTaste(), events }),
    });
    if (!res.ok) return null;
    const out = await res.json() as { raw: TasteRaw; compact: string };
    setTaste(out.raw, out.compact);
    return out.raw;
  } catch {
    return null;
  }
}

export function openPanel(cfg: TasteConfig, doc: Document = document): HTMLElement {
  doc.querySelector('fb-preferences')?.remove();
  const host = doc.createElement('fb-preferences');
  const root = host.attachShadow({ mode: 'open' });
  const draw = (raw: TasteRaw | null) => {
    const dims = raw?.dims || {};
    const rows = Object.keys(OPTIONS).map((d) => {
      const cur = dims[d];
      const how = !cur ? 'not set' : cur.source === 'explicit' ? 'you chose this' : 'our guess from how you browse';
      const opts = ['<option value="">—</option>', ...OPTIONS[d].map((o) =>
        `<option value="${o}"${cur?.value === o ? ' selected' : ''}>${o}</option>`)].join('');
      return `<div class="row"><label for="p-${d}">${LABELS[d]}<small>${how}</small></label>` +
        `<select id="p-${d}" data-dim="${d}">${opts}</select></div>`;
    }).join('');
    root.innerHTML = `<style>${CSS}</style><div class="bg" part="backdrop"><div class="box" role="dialog" aria-modal="true" aria-labelledby="p-h">` +
      `<h2 id="p-h">Your preferences</h2><p>How pages and the agent present things to you. Prices and facts are the same for everyone.</p>` +
      `${rows}<div class="btns"><button data-act="forget">Forget me</button><button data-act="reset">Reset</button>` +
      `<button class="primary" data-act="close">Done</button></div></div></div>`;
    root.querySelectorAll('select').forEach((s) => s.addEventListener('change', async () => {
      const dim = s.getAttribute('data-dim') || '';
      const value = (s as HTMLSelectElement).value;
      draw(await send(cfg, [value ? { type: 'set', dim, value } : { type: 'reset', dim }]) || getTaste());
    }));
    root.querySelector('[data-act="reset"]')?.addEventListener('click', async () => {
      draw(await send(cfg, [{ type: 'reset' }]) || getTaste());
    });
    root.querySelector('[data-act="forget"]')?.addEventListener('click', async () => {
      const vid = visitorId();
      if (vid) {
        await fetch(`${cfg.api.replace(/\/$/, '')}/memory`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key: cfg.key || undefined, visitor: vid, remember: false }),
        }).catch(() => {});
      }
      setTaste({ dims: {}, interests: {} }, '');
      host.remove();
    });
    root.querySelector('[data-act="close"]')?.addEventListener('click', () => host.remove());
    root.querySelector('.bg')?.addEventListener('click', (e) => { if (e.target === e.currentTarget) host.remove(); });
  };
  draw(getTaste());
  doc.body.appendChild(host);
  (root.querySelector('select') as HTMLElement | null)?.focus();
  return host;
}
