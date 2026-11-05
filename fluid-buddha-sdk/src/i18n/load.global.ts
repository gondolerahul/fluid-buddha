// <script>-tag build of load.ts: the Hindi table ships as
// fluid-buddha-hi.global.js next to fluid-buddha.global.js.

import type { StringKey } from './index';
import { loadGlobal } from '../ui/scriptLoader';

export function loadHindi(): Promise<Record<StringKey, string>> {
  return loadGlobal<{ hi: Record<StringKey, string> }>('fluid-buddha-hi.global.js', 'FluidBuddhaHindi').then(
    (m) => m.hi,
  );
}
