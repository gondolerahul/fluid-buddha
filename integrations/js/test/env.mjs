// jsdom globals + a fake FluidBuddha server for the wrapper tests.
import { JSDOM } from 'jsdom';

export function setupDom(url = 'https://shop.example.com/') {
  const dom = new JSDOM('<!doctype html><html><head></head><body><div id="app"></div></body></html>', { url });
  const { window } = dom;
  globalThis.window = window;
  globalThis.document = window.document;
  Object.defineProperty(globalThis, 'navigator', { value: window.navigator, configurable: true });
  for (const k of ['HTMLElement', 'Element', 'Node', 'Event', 'CustomEvent', 'MutationObserver', 'SVGElement']) {
    globalThis[k] = window[k];
  }
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  return window;
}

/**
 * Pretend to be the server: when a page adds <server>/widget/loader.js, the
 * widget global appears and `fluidbuddha:ready` fires, like the real loader.
 */
export function fakeServer(window, { fail = false } = {}) {
  const state = { loads: [], inits: [], conversions: [] };
  const head = window.document.head;
  // Wrap the original each time, so a second fake replaces the first.
  head.__append = head.__append || head.appendChild.bind(head);
  const append = head.__append;
  head.appendChild = (node) => {
    const r = append(node);
    if (node.tagName === 'SCRIPT' && /\/widget\/loader\.js$/.test(node.src)) {
      state.loads.push({ src: node.src, auto: node.getAttribute('data-auto') });
      setTimeout(() => {
        if (fail) {
          node.onerror && node.onerror(new window.Event('error'));
          return;
        }
        window.FluidBuddha = {
          init(opts) {
            state.inits.push(opts);
            const el = window.document.createElement('fluid-buddha');
            window.document.body.appendChild(el);
            return el;
          },
          conversion(name) {
            state.conversions.push(name);
          },
        };
        window.dispatchEvent(new window.Event('fluidbuddha:ready'));
      }, 5);
    }
    return r;
  };
  return state;
}

export const wait = (ms = 40) => new Promise((r) => setTimeout(r, ms));
export const CODE = 'https://fbk_abcdefgh12345678@agent.example.com';
export const widgets = () => globalThis.document.querySelectorAll('fluid-buddha').length;
