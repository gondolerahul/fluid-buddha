// @fluidbuddha/vue against a fake server.
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom, fakeServer, wait, CODE, widgets } from './env.mjs';

const window = setupDom();
const { createApp, h, ref, nextTick } = await import('vue');
const { FluidBuddha, FbRegion } = await import('../packages/vue/dist/index.mjs');

test('mounts the widget, follows prop changes, and removes it on unmount', async () => {
  const state = fakeServer(window);
  const routed = [];
  const position = ref('bottom-left');
  const app = createApp({
    render: () => h(FluidBuddha, { installCode: CODE, position: position.value, lang: 'hi',
      onNavigate: (p) => routed.push(p) }),
  });
  app.mount(window.document.getElementById('app'));
  await wait();
  assert.equal(state.loads.length, 1);
  assert.equal(state.loads[0].src, 'https://agent.example.com/widget/loader.js');
  assert.equal(widgets(), 1);
  const opts = state.inits.at(-1);
  assert.equal(opts.key, 'fbk_abcdefgh12345678');
  assert.equal(opts.backend, 'wss://agent.example.com');
  assert.equal(opts.position, 'bottom-left');
  assert.equal(opts.lang, 'hi');
  assert.equal('autoStart' in opts, false, 'unset booleans are left to the site');
  opts.hooks.onNavigate('/fees');
  assert.deepEqual(routed, ['/fees'], '@navigate receives the route');
  assert.equal(opts.hooks.onScrollTo, undefined);

  position.value = 'bottom-right';
  await nextTick();
  await wait();
  assert.equal(state.inits.length, 2);
  assert.equal(state.inits.at(-1).position, 'bottom-right');
  assert.equal(widgets(), 1);

  app.unmount();
  assert.equal(widgets(), 0);
});

test('a server that is down is reported', async () => {
  delete window.FluidBuddha;
  const state = fakeServer(window, { fail: true });
  const errors = [];
  const app = createApp({
    render: () => h(FluidBuddha, { installCode: 'https://fbk_failing12345678@down.example.com',
      onError: (e) => errors.push(e.message) }),
  });
  app.mount(window.document.getElementById('app'));
  await wait();
  assert.equal(state.loads.length, 1);
  assert.match(errors[0], /could not load https:\/\/down\.example\.com\/widget\/loader\.js/);
  assert.equal(widgets(), 0);
  app.unmount();
});

test('FbRegion renders an <fb-region> with the slot content inside', async () => {
  const app = createApp({ render: () => h(FbRegion, { name: 'proof' }, () => [h('p', 'Our own proof')]) });
  app.mount(window.document.getElementById('app'));
  await nextTick();
  const el = window.document.querySelector('fb-region');
  assert.equal(el.getAttribute('name'), 'proof');
  assert.equal(el.querySelector('p').textContent, 'Our own proof');
  app.unmount();
});
