// Renders a full runtime-generated PageSpec (Extreme intelligence) into a
// design-system-themed surface, section by section with incremental reveal
// (Req 3.5.2 generalised to whole pages). The agent never emits HTML — it emits
// typed sections that map to these safe renderers. Section types mirror the
// backend catalogue in app/orchestrator/pagegen.py.

import { PageSection, PageSpec } from '../../protocol';
import { buildChart } from '../components/chart';
import { buildFlowchart } from '../components/flowchart';
import { revealSequence } from '../components/reveal';

export interface EnquiryPayload {
  operationId?: string;
  values: Record<string, string>;
}

export class PageRenderer {
  constructor(
    private readonly container: HTMLElement,
    private readonly onEnquiry: (payload: EnquiryPayload) => void,
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
    submit.textContent = str(p.submit_label) || 'Submit';
    form.appendChild(submit);
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const values: Record<string, string> = {};
      inputs.forEach(({ name, el }) => (values[name] = el.value));
      this.onEnquiry({ operationId: str(p.operation_id) || undefined, values });
      submit.textContent = 'Sent ✓';
      submit.disabled = true;
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
function append(parent: HTMLElement, child: HTMLElement | null): void {
  if (child) parent.appendChild(child);
}
