// <script>-tag build of load.ts: the regions controller ships as
// fluid-buddha-regions.global.js next to fluid-buddha.global.js.

import type { createController } from './controller';
import { loadGlobal } from '../../ui/scriptLoader';

export function loadRegions(): Promise<{ createController: typeof createController }> {
  return loadGlobal<{ createController: typeof createController }>(
    'fluid-buddha-regions.global.js', 'FluidBuddhaRegions');
}
