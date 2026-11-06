// @fluidbuddha/react against a fake server.
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupDom, fakeServer, wait, CODE, widgets } from './env.mjs';

const window = setupDom();
const state = fakeServer(window);
const React = await import('react');
const { createRoot } = await import('react-dom/client');
const { act } = React;
const { FluidBuddha, conversion } = await import('../packages/react/dist/index.mjs');

const h = React.createElement;

async function render(el) {
  const root = createRoot(window.document.getElementById('app'));
  await act(async () => root.render(el));
  await act(async () => wait());
  return root;
}

test('mounts the widget from the install code, with hooks', async () => {
  const routed = [];
  const root = await render(h(FluidBuddha, { installCode: CODE, position: 'bottom-left',
    onNavigate: (p) => routed.push(p) }));
  assert.equal(state.loads.length, 1);
  assert.equal(state.loads[0].src, 'https://agent.example.com/widget/loader.js');
  assert.equal(state.loads[0].auto, 'false', 'the wrapper creates the widget itself');
  assert.equal(widgets(), 1);
  const opts = state.inits.at(-1);
  assert.equal(opts.backend, 'wss://agent.example.com');
  assert.equal(opts.api, 'https://agent.example.com');
  assert.equal(opts.key, 'fbk_abcdefgh12345678');
  assert.equal(opts.position, 'bottom-left');
  assert.equal('design' in opts, false, "options left out come from the site's settings");
  opts.hooks.onNavigate('/pricing');
  assert.deepEqual(routed, ['/pricing']);
  assert.equal(opts.hooks.onSetPersona, undefined, 'hooks not given stay unset');

  // New callbacks on re-render don't recreate the widget.
  const later = [];
  await act(async () => root.render(h(FluidBuddha, { installCode: CODE, position: 'bottom-left',
    onNavigate: (p) => later.push(p) })));
  await act(async () => wait());
  assert.equal(state.inits.length, 1);
  opts.hooks.onNavigate('/demo');
  assert.deepEqual(later, ['/demo'], 'the latest callback is used');

  // A changed option does.
  await act(async () => root.render(h(FluidBuddha, { installCode: CODE, position: 'bottom-right' })));
  await act(async () => wait());
  assert.equal(state.inits.length, 2);
  assert.equal(widgets(), 1);

  await act(async () => root.unmount());
  assert.equal(widgets(), 0, 'unmounting removes the widget');
  assert.equal(state.loads.length, 1, 'the code is loaded once per page');
});

test('StrictMode leaves exactly one widget', async () => {
  const before = state.inits.length;
  const root = await render(h(React.StrictMode, null, h(FluidBuddha, { installCode: CODE })));
  assert.equal(widgets(), 1);
  assert.ok(state.inits.length - before >= 1);
  await act(async () => root.unmount());
  assert.equal(widgets(), 0);
});

test('a bad install code reports an error and adds nothing', async () => {
  const errors = [];
  const root = await render(h(FluidBuddha, { installCode: 'fbk_missing_server_1', onError: (e) => errors.push(e.message) }));
  assert.match(errors[0], /invalid install code/);
  assert.equal(widgets(), 0);
  await act(async () => root.unmount());
});

test('conversion reports a goal through the widget', () => {
  conversion('demo_booked');
  assert.deepEqual(state.conversions, ['demo_booked']);
});
