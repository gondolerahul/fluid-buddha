// Public entry point.
//
//   <script src="fluid-buddha.global.js" data-backend="wss://voice.example.com"
//           data-key="fbk_..."></script>
//
// auto-injects the overlay. `data-key` is the website's widget key from the
// console's Install tab; built-in demo sites can use `data-site` instead. Or
// programmatically:
//
//   import { init } from 'fluid-buddha';
//   init({ backend: 'wss://voice.example.com', site: 'hirebuddha',
//          hooks: { onSetPersona: (p) => myStore.setICP(p) } });

import { FluidBuddhaElement } from './ui/FluidBuddhaElement';
import { FluidBuddhaOptions, optionsFromAttributes } from './core/config';

export const VERSION = '0.1.0';
export { FluidBuddhaElement };
export { Session } from './core/Session';
export { HostBridge } from './core/HostBridge';
export { Canvas } from './ui/components/canvas';
// For hosts that build their own UI around Session (requestConsent).
export { consentCopy, consentPrompt } from './ui/consent';
// For hosts with their own capture or transport: the VAD + pre-roll gate and
// the binary audio frame format.
export { SpeechGate } from './audio/SpeechGate';
export { packAudio, unpackAudio } from './protocol';
export type {
  FluidBuddhaConfig,
  FluidBuddhaOptions,
  FluidBuddhaHooks,
  IntelligenceLevel,
  DesignLevel,
  NavigationMode,
} from './core/config';
export type {
  Envelope,
  ComponentPayload,
  ComponentType,
  PageSpec,
  PageSection,
  Grounding,
  Privacy,
} from './protocol';

function defineElement(): void {
  if (typeof customElements !== 'undefined' && !customElements.get(FluidBuddhaElement.tagName)) {
    customElements.define(FluidBuddhaElement.tagName, FluidBuddhaElement);
  }
}

/** Create, configure and inject a <fluid-buddha> overlay; returns the element. */
export function init(options: FluidBuddhaOptions = {}): FluidBuddhaElement {
  defineElement();
  const el = document.createElement(FluidBuddhaElement.tagName) as FluidBuddhaElement;
  el.options = options;
  document.body.appendChild(el);
  return el;
}

defineElement();

// Auto-init when injected as a <script data-backend=...> tag.
function autoInit(): void {
  if (typeof document === 'undefined') return;
  // Prefer the injecting script (normally carries the data-* attrs); fall back
  // to any script that declares data-backend (e.g. bundled/inlined setups).
  let script = document.currentScript as HTMLScriptElement | null;
  if (!script || !script.getAttribute('data-backend')) {
    script = document.querySelector<HTMLScriptElement>('script[data-backend]');
  }
  const opts = optionsFromAttributes(script);
  if (!opts.backend || opts.autoInject === false) return;
  const run = () => init(opts);
  if (document.body) run();
  else document.addEventListener('DOMContentLoaded', run, { once: true });
}
autoInit();

export default { init, VERSION };
