// The recap page's renderer (M2-6). Built as its own small script
// (dist/fluid-buddha-recap.global.js) so the widget doesn't carry it.
//
// The backend's recap page has, for each component shown in the conversation,
// a slot (<div data-fb-slot="c0">) and the component specs in a JSON block
// (<script type="application/json" id="fb-recap-data">). This draws each one
// with the widget's own renderers, in a shadow root with the widget's styles,
// replacing the text fallback. Components stay interactive (sliders etc.);
// nothing is sent anywhere.

import { ComponentPayload } from './protocol';
import { Canvas, provideBodies } from './ui/components/canvas';
import { buildBody } from './ui/components/bodies';

provideBodies(buildBody);
import { COMMON_STYLES, CORE_STYLES } from './ui/styles';

interface Slot {
  slot: string;
  component: ComponentPayload;
}

export function renderRecap(doc: Document = document): number {
  let slots: Slot[] = [];
  try {
    slots = JSON.parse(doc.getElementById('fb-recap-data')?.textContent || '[]');
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
      new Canvas(box, () => undefined).add({ ...s.component, sync_id: s.component.sync_id || `recap_${i}` });
      drawn++;
    } catch {
      /* leave the text fallback */
    }
  });
  return drawn;
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => renderRecap());
  else renderRecap();
}
