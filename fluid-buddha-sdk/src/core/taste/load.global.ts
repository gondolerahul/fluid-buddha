// <script>-tag build of load.ts: the panel ships as fluid-buddha-prefs.global.js.

import type { openPanel } from './panel';
import { loadGlobal } from '../../ui/scriptLoader';

export function loadPanel(): Promise<{ openPanel: typeof openPanel }> {
  return loadGlobal<{ openPanel: typeof openPanel }>('fluid-buddha-prefs.global.js', 'FluidBuddhaPrefs');
}
