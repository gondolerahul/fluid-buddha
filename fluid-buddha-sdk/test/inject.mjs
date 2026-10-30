// End-to-end check that the built IIFE auto-injects into an arbitrary host
// page from a single <script> tag (the framework-agnostic promise).
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const bundle = readFileSync(new URL('../dist/fluid-buddha.global.js', import.meta.url), 'utf8');

const html = `<!doctype html><html><body>
  <h1>Some unrelated host site</h1>
  <section id="pricing">pricing</section>
  <script data-backend="ws://localhost:8080" data-site="hirebuddha" data-accent="#c9a24a"></script>
  <script>${bundle}</script>
</body></html>`;

const dom = new JSDOM(html, { runScripts: 'dangerously', url: 'http://localhost/' });
const { document } = dom.window;

let failures = 0;
const ok = (cond, msg) => { console.log(`${cond ? 'PASS' : 'FAIL'}  ${msg}`); if (!cond) failures++; };

const el = document.querySelector('fluid-buddha');
ok(!!el, 'a <fluid-buddha> element was auto-injected into <body>');
ok(!!el && !!el.shadowRoot, 'the injected element built a Shadow DOM');
ok(!!el && !!el.shadowRoot.querySelector('.trigger'), 'the floating trigger rendered inside the shadow root');
ok(typeof dom.window.FluidBuddha?.init === 'function', 'window.FluidBuddha.init is exposed');

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
