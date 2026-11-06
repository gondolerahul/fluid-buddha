// @fluidbuddha/components: React component → Web Component + manifest entry (P0-8).
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { setupDom, wait } from './env.mjs';

const window = setupDom();
globalThis.customElements = window.customElements;
globalThis.ShadowRoot = window.ShadowRoot;
const React = await import('react');
const { act } = React;
const { defineFbComponent, buildManifest, manifestEntryFor } = await import('../packages/components/dist/index.mjs');
const cli = await import('../packages/components/bin/fb-manifest.mjs');

const h = React.createElement;

function PlanTable({ title, tiers = [] }) {
  return h('section', null, title ? h('h2', null, title) : null,
    ...tiers.map((t) => h('div', { key: t.name, className: 'tier' }, `${t.name}: ${t.price}`)));
}

const def = defineFbComponent(PlanTable, {
  id: 'acme.PlanTable', tag: 'acme-plan-table', purpose: 'Compare plans', useWhen: ['compare_plans'],
  props: {
    title: { type: 'string', source: 'model_text', maxLength: 120 },
    tiers: { type: 'array', source: 'binding_only', required: true, maxItems: 4 },
  },
  styles: ':host{display:block}',
});

test('manifest entry from the declaration', () => {
  assert.deepEqual(def.entry, {
    id: 'acme.PlanTable', renderer: 'wc:acme-plan-table', purpose: 'Compare plans',
    use_when: ['compare_plans'], avoid_when: [], version: 1,
    props: {
      title: { type: 'string', source: 'model_text', max_length: 120 },
      tiers: { type: 'array', source: 'binding_only', required: true, max_items: 4 },
    },
  });
  assert.throws(() => manifestEntryFor({ id: 'nodots', tag: 'a-b', props: {} }), /dotted/);
  assert.throws(() => manifestEntryFor({ id: 'a.B', tag: 'nodash', props: {} }), /dash/);
  assert.throws(() => manifestEntryFor({ id: 'a.B', tag: 'fb-thing', props: {} }), /fb-/);
});

test('registers a custom element that renders the React component from properties', async () => {
  assert.ok(window.customElements.get('acme-plan-table'));
  // Props set before the element is upgraded are picked up too.
  const el = window.document.createElement('acme-plan-table');
  el.tiers = [{ name: 'Scale', price: '₹9,999' }];
  el.title = 'Plans';
  await act(async () => { window.document.body.appendChild(el); await wait(10); });
  const root = el.shadowRoot;
  assert.ok(root, 'renders into a shadow root');
  assert.equal(root.querySelector('style').textContent, ':host{display:block}');
  assert.equal(root.querySelector('h2').textContent, 'Plans');
  assert.equal(root.querySelectorAll('.tier').length, 1);
  await act(async () => { el.tiers = [{ name: 'A', price: '1' }, { name: 'B', price: '2' }]; await wait(10); });
  assert.equal(root.querySelectorAll('.tier').length, 2, 're-renders when a property changes');
  assert.ok(Array.isArray(el.tiers));
  await act(async () => { el.remove(); await wait(10); });
});

test('upgrades properties set before definition', async () => {
  const el = window.document.createElement('acme-late-card');
  el.title = 'Early';                 // a built-in property: lands as an attribute
  el.items = [{ name: 'x' }];         // an own property until the upgrade
  window.document.body.appendChild(el);
  function Card({ title, items = [] }) { return h('p', null, `${title}:${items.length}`); }
  await act(async () => {
    defineFbComponent(Card, { id: 'acme.LateCard', tag: 'acme-late-card',
      props: { title: { type: 'string' }, items: { type: 'array' } } });
    await wait(10);
  });
  assert.equal(el.shadowRoot.querySelector('p').textContent, 'Early:1');
});

test('buildManifest and the fb-manifest CLI', async () => {
  const m = buildManifest([def], { bundle: { url: 'https://cdn.example.com/x.js', integrity: 'sha384-abc' } });
  assert.equal(m.include_defaults, true);
  assert.equal(m.components[0].id, 'acme.PlanTable');
  assert.throws(() => buildManifest([def, def]), /Duplicate/);

  const dir = mkdtempSync(path.join(tmpdir(), 'fbm-'));
  const bundle = path.join(dir, 'bundle.js');
  writeFileSync(bundle, 'console.log("components")');
  const mod = path.join(dir, 'defs.mjs');
  writeFileSync(mod, `export const PlanTable = ${JSON.stringify(def)};\nexport const other = 42;\n`);
  const out = path.join(dir, 'manifest.json');
  await cli.main(['--module', mod, '--bundle-file', bundle, '--bundle-url', 'https://cdn.example.com/b.js', '--out', out]);
  const written = JSON.parse(readFileSync(out, 'utf8'));
  assert.equal(written.components.length, 1);
  assert.equal(written.bundle.url, 'https://cdn.example.com/b.js');
  assert.equal(written.bundle.integrity, cli.sriHash(readFileSync(bundle)));
  assert.match(written.bundle.integrity, /^sha384-[A-Za-z0-9+/]+=*$/);
  await assert.rejects(cli.main(['--module', mod, '--bundle-file', bundle, '--bundle-url', 'http://x']), /https/);
  const empty = path.join(dir, 'empty.mjs');
  writeFileSync(empty, 'export const x = 1;\n');
  await assert.rejects(cli.main(['--module', empty]), /No defineFbComponent/);
  assert.ok(pathToFileURL(mod));
});

test('replaces a server-rendered declarative fallback when it upgrades', async () => {
  const el = window.document.createElement('acme-ssr-card');
  const shadow = el.attachShadow({ mode: 'open' });
  shadow.innerHTML = '<div class="fb-fallback">Readable fallback</div>';
  el.title = 'Live';
  window.document.body.appendChild(el);
  function Card({ title }) { return h('p', { className: 'live' }, title); }
  await act(async () => {
    defineFbComponent(Card, { id: 'acme.SsrCard', tag: 'acme-ssr-card', props: { title: { type: 'string' } } });
    await wait(10);
  });
  assert.equal(el.shadowRoot.querySelector('.fb-fallback'), null);
  assert.equal(el.shadowRoot.querySelector('.live').textContent, 'Live');
});
