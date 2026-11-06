// Renders a full runtime-generated PageSpec (Extreme intelligence) into a
// design-system-themed surface, section by section with incremental reveal
// (Req 3.5.2 generalised to whole pages). The agent never emits HTML — it emits
// typed sections that map to these safe renderers. Section types mirror the
// backend catalogue in app/orchestrator/pagegen.py.

import { PageSection, PageSpec } from '../../protocol';
import { buildChart } from '../components/chart';
import { buildFlowchart } from '../components/flowchart';
import { buildRoiCalculator } from '../components/roiCalculator';
import { revealSequence } from '../components/reveal';
import { t } from '../../i18n';

export interface EnquiryPayload {
  operationId?: string;
  values: Record<string, string>;
}

export class PageRenderer {
  constructor(
    private readonly container: HTMLElement,
    /** Resolves true once the enquiry is stored (a lead), false on failure. */
    private readonly onEnquiry: (payload: EnquiryPayload) => Promise<boolean>,
  ) {}

  render(page: PageSpec): void {
    this.container.replaceChildren();
    const built: HTMLElement[] = [];
    for (const section of page.sections || []) {
      const el = this.buildSection(section);
      if (el) {
        this.container.appendChild(el);
        built.push(el);
      }
    }
    revealSequence(built, { stepMs: 320 });
  }

  private buildSection(section: PageSection): HTMLElement | null {
    const p = section.props || {};
    const wrap = document.createElement('section');
    wrap.className = `fbpage-section fbpage-${section.type}`;
    switch (section.type) {
      case 'hero': return this.hero(wrap, p);
      case 'feature_grid': return this.featureGrid(wrap, p);
      case 'text': return this.text(wrap, p);
      case 'pricing_table': return this.pricing(wrap, p);
      case 'chart': wrap.appendChild(buildChart(p)); return wrap;
      case 'flowchart': wrap.appendChild(buildFlowchart(p)); return wrap;
      case 'enquiry_form': return this.enquiry(wrap, p);
      case 'cta': return this.cta(wrap, p);
      case 'media': return this.media(wrap, p);
      // M3-1: landing-page sections.
      case 'testimonials': return this.testimonials(wrap, p);
      case 'logos': return this.logos(wrap, p);
      case 'faq': return this.faq(wrap, p);
      case 'comparison': return this.comparison(wrap, p);
      case 'roi_calculator':
        append(wrap, this.heading('h2', p.title, 'fbpage-h2'));
        wrap.appendChild(buildRoiCalculator(p));
        return wrap;
      default: return null;
    }
  }

  private heading(tag: 'h1' | 'h2' | 'h3', text: unknown, cls: string): HTMLElement | null {
    const t = str(text);
    if (!t) return null;
    const h = document.createElement(tag);
    h.className = cls;
    h.textContent = t;
    return h;
  }

  private hero(wrap: HTMLElement, p: Record<string, unknown>): HTMLElement {
    append(wrap, this.heading('h1', p.title, 'fbpage-hero-title'));
    const sub = str(p.subtitle);
    if (sub) {
      const s = document.createElement('p');
      s.className = 'fbpage-hero-sub';
      s.textContent = sub;
      wrap.appendChild(s);
    }
    const cta = str(p.cta_label);
    if (cta) wrap.appendChild(this.ctaButton(cta));
    return wrap;
  }

  private featureGrid(wrap: HTMLElement, p: Record<string, unknown>): HTMLElement {
    append(wrap, this.heading('h2', p.title, 'fbpage-h2'));
    const grid = document.createElement('div');
    grid.className = 'fbpage-grid';
    for (const item of asArray(p.items)) {
      const card = document.createElement('div');
      card.className = 'fbpage-card';
      append(card, this.heading('h3', item.title, 'fbpage-card-title'));
      const body = str(item.body);
      if (body) { const b = document.createElement('p'); b.textContent = body; card.appendChild(b); }
      grid.appendChild(card);
    }
    wrap.appendChild(grid);
    return wrap;
  }

  private text(wrap: HTMLElement, p: Record<string, unknown>): HTMLElement {
    append(wrap, this.heading('h2', p.title, 'fbpage-h2'));
    const body = str(p.body);
    if (body) { const b = document.createElement('p'); b.className = 'fbpage-body'; b.textContent = body; wrap.appendChild(b); }
    return wrap;
  }

  private pricing(wrap: HTMLElement, p: Record<string, unknown>): HTMLElement {
    append(wrap, this.heading('h2', p.title, 'fbpage-h2'));
    const row = document.createElement('div');
    row.className = 'fbpage-grid';
    for (const tier of asArray(p.tiers)) {
      const card = document.createElement('div');
      card.className = 'fbpage-card fbpage-tier';
      append(card, this.heading('h3', tier.name, 'fbpage-card-title'));
      const price = str(tier.price);
      if (price) { const pr = document.createElement('div'); pr.className = 'fbpage-price'; pr.textContent = price; card.appendChild(pr); }
      const ul = document.createElement('ul');
      ul.className = 'fbpage-features';
      for (const f of asArray<string>(tier.features)) {
        const li = document.createElement('li');
        li.textContent = String(f);
        ul.appendChild(li);
      }
      card.appendChild(ul);
      row.appendChild(card);
    }
    wrap.appendChild(row);
    return wrap;
  }

  private enquiry(wrap: HTMLElement, p: Record<string, unknown>): HTMLElement {
    append(wrap, this.heading('h2', p.title, 'fbpage-h2'));
    const form = document.createElement('form');
    form.className = 'fbpage-form';
    const inputs: Array<{ name: string; el: HTMLInputElement | HTMLTextAreaElement }> = [];
    for (const field of asArray(p.fields)) {
      const name = str(field.name) || 'field';
      const label = document.createElement('label');
      label.className = 'fbpage-field';
      label.textContent = str(field.label) || name;
      const type = str(field.type) || 'text';
      const input = type === 'textarea'
        ? document.createElement('textarea')
        : Object.assign(document.createElement('input'), { type });
      input.name = name;
      label.appendChild(input);
      form.appendChild(label);
      inputs.push({ name, el: input });
    }
    const submit = document.createElement('button');
    submit.type = 'submit';
    submit.className = 'fbpage-btn';
    submit.textContent = str(p.submit_label) || t('submit');
    form.appendChild(submit);
    const label = submit.textContent;
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const values: Record<string, string> = {};
      inputs.forEach(({ name, el }) => (values[name] = el.value));
      submit.disabled = true;
      submit.textContent = t('sending');
      void this.onEnquiry({ operationId: str(p.operation_id) || undefined, values }).then((ok) => {
        submit.textContent = t(ok ? 'sent' : 'tryAgain');
        submit.disabled = ok;
        if (!ok) setTimeout(() => { if (!submit.disabled) submit.textContent = label; }, 4000);
      });
    });
    wrap.appendChild(form);
    return wrap;
  }

  private cta(wrap: HTMLElement, p: Record<string, unknown>): HTMLElement {
    append(wrap, this.heading('h2', p.title, 'fbpage-h2'));
    const body = str(p.body);
    if (body) { const b = document.createElement('p'); b.className = 'fbpage-body'; b.textContent = body; wrap.appendChild(b); }
    const cta = str(p.cta_label);
    if (cta) wrap.appendChild(this.ctaButton(cta));
    return wrap;
  }

  private media(wrap: HTMLElement, p: Record<string, unknown>): HTMLElement {
    const src = str(p.src);
    if (src) {
      const img = document.createElement('img');
      img.className = 'fbpage-media';
      img.src = src;
      img.alt = str(p.alt) || '';
      wrap.appendChild(img);
    }
    const cap = str(p.caption);
    if (cap) { const c = document.createElement('div'); c.className = 'fbpage-caption'; c.textContent = cap; wrap.appendChild(c); }
    return wrap;
  }

  private testimonials(wrap: HTMLElement, p: Record<string, unknown>): HTMLElement {
    append(wrap, this.heading('h2', p.title, 'fbpage-h2'));
    const grid = el('div', 'fbpage-grid');
    for (const item of asArray(p.items)) {
      const fig = el('figure', 'fbpage-card fbpage-quote');
      fig.appendChild(el('blockquote', '', str(item.quote)));
      const who = [str(item.name), str(item.role)].filter(Boolean).join(', ');
      fig.appendChild(el('figcaption', '', who));
      grid.appendChild(fig);
    }
    wrap.appendChild(grid);
    return wrap;
  }

  private logos(wrap: HTMLElement, p: Record<string, unknown>): HTMLElement {
    append(wrap, this.heading('h2', p.title, 'fbpage-h2'));
    const row = el('div', 'fbpage-logos');
    for (const item of asArray(p.items)) {
      const src = str(item.src);
      if (!src.startsWith('https://')) continue;
      const img = document.createElement('img');
      img.src = src;
      img.alt = str(item.alt);
      img.loading = 'lazy';
      row.appendChild(img);
    }
    wrap.appendChild(row);
    return wrap;
  }

  private faq(wrap: HTMLElement, p: Record<string, unknown>): HTMLElement {
    append(wrap, this.heading('h2', p.title, 'fbpage-h2'));
    asArray(p.items).forEach((item, i) => {
      const d = el('details', 'fbpage-card fbpage-qa') as HTMLDetailsElement;
      d.open = i === 0;
      d.appendChild(el('summary', '', str(item.q)));
      d.appendChild(el('p', '', str(item.a)));
      wrap.appendChild(d);
    });
    return wrap;
  }

  private comparison(wrap: HTMLElement, p: Record<string, unknown>): HTMLElement {
    append(wrap, this.heading('h2', p.title, 'fbpage-h2'));
    const table = document.createElement('table');
    table.className = 'fbpage-table';
    const head = table.createTHead().insertRow();
    head.appendChild(el('th', ''));
    for (const c of asArray<string>(p.columns)) head.appendChild(el('th', '', str(c)));
    const body = table.createTBody();
    for (const r of asArray(p.rows)) {
      const tr = body.insertRow();
      const th = el('th', '', str(r.label));
      th.setAttribute('scope', 'row');
      tr.appendChild(th);
      for (const v of asArray<string>(r.values)) tr.appendChild(el('td', '', str(v)));
    }
    const scroll = el('div', 'fbpage-scroll');
    scroll.appendChild(table);
    wrap.appendChild(scroll);
    return wrap;
  }

  private ctaButton(label: string): HTMLButtonElement {
    const btn = document.createElement('button');
    btn.className = 'fbpage-btn';
    btn.textContent = label;
    // A CTA scrolls to an enquiry form if present, else is a no-op affordance.
    btn.addEventListener('click', () => {
      this.container.querySelector('.fbpage-form')?.scrollIntoView({ behavior: 'smooth' });
    });
    return btn;
  }
}

// ---- small helpers ----
function str(v: unknown): string {
  return typeof v === 'string' ? v : v == null ? '' : String(v);
}
function asArray<T = Record<string, unknown>>(v: unknown): T[] {
  return Array.isArray(v) ? (v as T[]) : [];
}
function el(tag: string, cls: string, text?: string): HTMLElement {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text) e.textContent = text;
  return e;
}
function append(parent: HTMLElement, child: HTMLElement | null): void {
  if (child) parent.appendChild(child);
}
