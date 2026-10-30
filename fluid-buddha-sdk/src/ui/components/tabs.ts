// Tabbed explorer — lets the visitor flip between panels of content at their own
// pace. Content is plain text (safe), set via textContent.

import { RenderContext } from './interactive';

interface Tab { label?: string; body?: string }

export function buildTabs(state: Record<string, unknown>, ctx?: RenderContext): HTMLElement {
  const tabs = (state.tabs as Tab[] | undefined) ?? [];
  const root = document.createElement('div');
  root.className = 'tabs';
  if (!tabs.length) {
    root.innerHTML = '<div class="empty">No tabs.</div>';
    return root;
  }

  const bar = document.createElement('div');
  bar.className = 'tabs-bar';
  bar.setAttribute('role', 'tablist');
  const panel = document.createElement('div');
  panel.className = 'tabs-panel';

  const btns: HTMLButtonElement[] = [];
  const select = (i: number) => {
    btns.forEach((b, j) => {
      b.classList.toggle('active', j === i);
      b.setAttribute('aria-selected', String(j === i));
    });
    panel.textContent = tabs[i]?.body ?? '';
    ctx?.reportState?.({ tab: i, label: tabs[i]?.label ?? '' });
  };

  tabs.forEach((t, i) => {
    const b = document.createElement('button');
    b.className = 'tabs-tab';
    b.type = 'button';
    b.setAttribute('role', 'tab');
    b.textContent = t.label ?? `Tab ${i + 1}`;
    b.addEventListener('click', () => select(i));
    bar.appendChild(b);
    btns.push(b);
  });

  root.append(bar, panel);
  select(0);
  return root;
}
