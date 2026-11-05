// Install codes and the server's loader script (M2-10).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { setupDom } from './env.mjs';

const window = setupDom();
const { parseInstallCode } = await import('../packages/react/dist/index.mjs');

test('install codes carry the server and the key', () => {
  assert.deepEqual(parseInstallCode('https://fbk_abcdefgh12345678@agent.example.com'),
    { server: 'https://agent.example.com', key: 'fbk_abcdefgh12345678' });
  assert.deepEqual(parseInstallCode('  https://fbk_abcdefgh12345678@agent.example.com/fb/  '),
    { server: 'https://agent.example.com/fb', key: 'fbk_abcdefgh12345678' });
  assert.deepEqual(parseInstallCode('http://fbk_abcdefgh-_12345@localhost:8081'),
    { server: 'http://localhost:8081', key: 'fbk_abcdefgh-_12345' });
  // A bare key needs its server.
  assert.equal(parseInstallCode('fbk_abcdefgh12345678'), null);
  assert.deepEqual(parseInstallCode('fbk_abcdefgh12345678', 'https://agent.example.com/'),
    { server: 'https://agent.example.com', key: 'fbk_abcdefgh12345678' });
});

test('anything else is refused', () => {
  const bad = ['', 'hello', 'https://agent.example.com', 'https://notakey@agent.example.com',
    'javascript://fbk_abcdefgh12345678@x', 'ftp://fbk_abcdefgh12345678@x.example',
    'https://fbk_abcdefgh12345678@agent.example.com?x=1', 'https://fbk_abcdefgh12345678@agent.example.com#a',
    'https://fbk_abc"><script>@agent.example.com'];
  for (const code of bad) assert.equal(parseInstallCode(code), null, code);
  assert.equal(parseInstallCode('fbk_abcdefgh12345678', 'javascript:alert(1)'), null);
});

// The real loader, exactly as the backend serves it (app/routes/widget.py).
function backendLoader(sdk) {
  const py = readFileSync(new URL('../../../backend/app/routes/widget.py', import.meta.url), 'utf8');
  const m = /_LOADER = r"""([\s\S]*?)"""/.exec(py);
  assert.ok(m, 'loader source found in widget.py');
  return m[1].replace('__SDK__', JSON.stringify(sdk));
}

function runLoader(src, attrs = {}) {
  window.__fluidBuddhaLoader = undefined;
  delete window.FluidBuddha;
  const me = window.document.createElement('script');
  me.src = src;
  for (const [k, v] of Object.entries(attrs)) me.setAttribute(k, v);
  Object.defineProperty(window.document, 'currentScript', { value: me, configurable: true });
  const before = new Set(window.document.head.querySelectorAll('script'));
  window.eval(backendLoader('https://cdn.example.com/dist/fluid-buddha.global.js'));
  return [...window.document.head.querySelectorAll('script')].find((s) => !before.has(s));
}

test('the loader adds the widget with the embed settings and its own server', () => {
  const sdk = runLoader('https://agent.example.com/widget/loader.js', {
    'data-key': 'fbk_abcdefgh12345678', 'data-position': 'bottom-left', id: 'x' });
  assert.equal(sdk.src, 'https://cdn.example.com/dist/fluid-buddha.global.js');
  assert.equal(sdk.getAttribute('data-key'), 'fbk_abcdefgh12345678');
  assert.equal(sdk.getAttribute('data-position'), 'bottom-left');
  assert.equal(sdk.getAttribute('data-backend'), 'wss://agent.example.com');
  assert.equal(sdk.getAttribute('data-api'), 'https://agent.example.com');
  assert.equal(sdk.getAttribute('id'), null, 'only data-* attributes are copied');
  let ready = 0;
  window.addEventListener('fluidbuddha:ready', () => ready++, { once: true });
  window.FluidBuddha = {};
  sdk.onload();
  assert.equal(ready, 1, 'fluidbuddha:ready fires once the widget code is in');
});

test('the loader reads settings from its query string (GTM) without overriding attributes', () => {
  const sdk = runLoader(
    'https://agent.example.com/sub/widget/loader.js?key=fbk_q1234567890&lang=hi&position=bottom-left&onload=evil',
    { 'data-position': 'bottom-right' });
  assert.equal(sdk.getAttribute('data-key'), 'fbk_q1234567890');
  assert.equal(sdk.getAttribute('data-lang'), 'hi');
  assert.equal(sdk.getAttribute('data-position'), 'bottom-right');
  assert.equal(sdk.getAttribute('data-onload'), null, 'unknown parameters are ignored');
  assert.equal(sdk.getAttribute('data-backend'), 'wss://agent.example.com/sub');
});

test('the loader runs once per page', () => {
  runLoader('https://agent.example.com/widget/loader.js');
  const count = window.document.head.querySelectorAll('script').length;
  window.eval(backendLoader('https://cdn.example.com/x.js')); // a second copy (plugin + manual snippet)
  assert.equal(window.document.head.querySelectorAll('script').length, count);
});
