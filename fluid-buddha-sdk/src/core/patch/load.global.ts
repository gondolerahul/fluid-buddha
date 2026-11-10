// <script>-tag build of load.ts: the patcher ships as
// fluid-buddha-patcher.global.js next to fluid-buddha.global.js.

import type { applyPatch, PageRenderer } from './patcher';
import { loadGlobal } from '../../ui/scriptLoader';

type Patcher = { applyPatch: typeof applyPatch; PageRenderer: typeof PageRenderer };

export function loadPatcher(): Promise<Patcher> {
  return loadGlobal<Patcher>('fluid-buddha-patcher.global.js', 'FluidBuddhaPatcher');
}
