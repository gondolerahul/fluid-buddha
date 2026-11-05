// Draws server-rendered component slots with the widget's own renderers, for
// pages the backend renders itself: the recap page (M2-6) and the hosted
// campaign page (M3-1).
//
// The page has, for each component, a slot (<div data-fb-slot="c0">) with a
// text fallback and the component specs in a JSON block
// (<script type="application/json" id="…">). Each is drawn in a shadow root
// with the widget's styles, replacing the fallback. Components stay
// interactive (sliders etc.); nothing is sent anywhere.

import { ComponentPayload } from './protocol';
import { Canvas, provideBodies } from './ui/components/canvas';
import { buildBody } from './ui/components/bodies';
import { COMMON_STYLES, CORE_STYLES } from './ui/styles';

provideBodies(buildBody);

interface Slot {
  slot: string;
  component: ComponentPayload;
}

export function renderSlots(doc: Document, dataId: string, prefix = 'slot'): number {
  let slots: Slot[] = [];
  try {
    slots = JSON.parse(doc.getElementById(dataId)?.textContent || '[]');
  } catch {
    return 0;
  }
  let drawn = 0;
  slots.forEach((s, i) => {
    const host = doc.querySelector<HTMLElement>(`[data-fb-slot="${s.slot}"]`);
    if (!host || !s.component || !s.component.component_type || host.shadowRoot) return;
    try {
      const root = host.attachShadow({ mode: 'open' });
      const style = doc.createElement('style');
      style.textContent = CORE_STYLES + COMMON_STYLES;
      const box = doc.createElement('div');
      box.className = 'fb-recap';
      root.append(style, box);
      new Canvas(box, () => undefined).add({ ...s.component, sync_id: s.component.sync_id || `${prefix}_${i}` });
      drawn++;
    } catch {
      /* leave the text fallback */
    }
  });
  return drawn;
}
