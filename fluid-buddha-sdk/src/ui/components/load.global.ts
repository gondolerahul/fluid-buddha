// <script>-tag build of load.ts: the renderers ship as
// fluid-buddha-components.global.js next to fluid-buddha.global.js.

import type { BuildBody } from './bodies';
import { loadGlobal } from '../scriptLoader';

export function loadBodies(): Promise<BuildBody> {
  return loadGlobal<{ buildBody: BuildBody }>('fluid-buddha-components.global.js', 'FluidBuddhaComponents').then(
    (m) => m.buildBody,
  );
}
