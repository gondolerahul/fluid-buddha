// The recap page's renderer (M2-6). Built as its own small script
// (dist/fluid-buddha-recap.global.js) so the widget doesn't carry it.
//
// The backend's recap page has, for each component shown in the conversation,
// a slot (<div data-fb-slot="c0">) and the component specs in a JSON block
// (<script type="application/json" id="fb-recap-data">); see ./slots.

import { renderSlots } from './slots';

export function renderRecap(doc: Document = document): number {
  return renderSlots(doc, 'fb-recap-data', 'recap');
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => renderRecap());
  else renderRecap();
}
