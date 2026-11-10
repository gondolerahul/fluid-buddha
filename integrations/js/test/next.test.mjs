// @fluidbuddha/next: fetch, handler, server component and metadata (Phase 2, P2-2).
import test from 'node:test';
import assert from 'node:assert/strict';

const React = await import('react');
const { renderToString } = await import('react-dom/server');
const { fetchComposedPage, createPageHandler, ComposedPage, composedMetadata, scriptJson } =
  await import('../packages/next/dist/index.mjs');

const CODE = 'https://fbk_abcdefgh12345678@agent.example.com';
const PAGE = {
  status: 200, plan_id: 'pl_0123456789', pending: false,
  html: '<main class="fbpage-root" data-fb-plan="pl_0123456789"><div class="fbpage-inner"><section data-fb-region="hero"><h1>Plans</h1></section></div></main>',
  css: ':root{--ds-color-primary:#123456}',
  head: { title: 'Pricing & plans', description: 'Compare plans', canonical: 'https://orbit.example/pricing',
          robots: 'index, follow', json_ld: { '@type': 'WebPage', name: '</script><b>' },
          markdown: 'https://agent.example.com/sites/fbk_abcdefgh12345678/views/pl_0123456789?format=md' },
  data: { plan_id: 'pl_0123456789', sections: [] },
  scripts: { composed: 'https://cdn.example.com/fluid-buddha-composed.global.js',
             loader: 'https://agent.example.com/widget/loader.js', key: 'fbk_abcdefgh12345678' },
};

function fakeFetch(body, calls, status = 200) {
  return async (url, init) => { calls.push({ url: String(url), init }); return { ok: status < 400, status, json: async () => body }; };
}

test('fetchComposedPage asks the server for the path with the visitor signals', async () => {
  const calls = [];
  const page = await fetchComposedPage({ installCode: CODE, fetch: fakeFetch(PAGE, calls) }, {
    path: '/pricing', searchParams: { utm_campaign: 'switch', q: 'vs rival', other: 'x', fbv: 'pl_0123456789' },
    headers: { 'user-agent': 'Googlebot/2.1', referer: 'https://www.google.com/',
               cookie: 'a=1; fbtaste=density%3Acompact%2Cdetail%3Asummary; b=2' } });
  const u = new URL(calls[0].url);
  assert.equal(u.origin + u.pathname, 'https://agent.example.com/experience/page');
  assert.equal(u.searchParams.get('key'), 'fbk_abcdefgh12345678');
  assert.equal(u.searchParams.get('path'), '/pricing');
  assert.equal(u.searchParams.get('utm_campaign'), 'switch');
  assert.equal(u.searchParams.get('fbv'), 'pl_0123456789');
  assert.equal(u.searchParams.get('other'), null);
  assert.equal(u.searchParams.get('ua'), 'Googlebot/2.1');
  assert.equal(u.searchParams.get('referrer'), 'https://www.google.com/');
  assert.equal(u.searchParams.get('taste'), 'density:compact,detail:summary');
  assert.equal(page.notFound, false);
  assert.equal(page.planId, 'pl_0123456789');
  await assert.rejects(fetchComposedPage({ installCode: 'nope' }, { path: '/' }), /invalid install code/);
});

test('failures and missing routes never throw', async () => {
  const calls = [];
  assert.equal((await fetchComposedPage({ installCode: CODE, fetch: fakeFetch({ status: 404 }, calls) }, { path: '/x' })).notFound, true);
  assert.equal((await fetchComposedPage({ installCode: CODE, fetch: fakeFetch({}, calls, 500) }, { path: '/x' })).status, 502);
  const down = async () => { throw new Error('offline'); };
  assert.equal((await fetchComposedPage({ installCode: CODE, fetch: down }, { path: '/x' })).status, 504);
});

test('the Route Handler returns the full document from your domain', async () => {
  const calls = [];
  const GET = createPageHandler({ installCode: CODE, fetch: fakeFetch(PAGE, calls), basePath: '/p' });
  const res = await GET(new Request('https://orbit.example/p/pricing?utm_source=google', { headers: { 'user-agent': 'Mozilla' } }));
  assert.equal(res.status, 200);
  assert.equal(new URL(calls[0].url).searchParams.get('path'), '/pricing');
  assert.equal(res.headers.get('cache-control'), 'private, no-store');
  assert.equal(res.headers.get('x-fluidbuddha-plan'), 'pl_0123456789');
  const html = await res.text();
  assert.match(html, /<title>Pricing &amp; plans<\/title>/);
  assert.match(html, /<link rel="canonical" href="https:\/\/orbit\.example\/pricing">/);
  assert.match(html, /id="fb-page-data"/);
  assert.match(html, /fluid-buddha-composed\.global\.js/);
  assert.match(html, /data-key="fbk_abcdefgh12345678"/);
  assert.ok(!html.includes('</script><b>'), 'JSON-LD is escaped');
  assert.match(html, /<link rel="alternate" type="text\/markdown" href="https:\/\/agent\.example\.com\/sites\/fbk_abcdefgh12345678\/views\/pl_0123456789\?format=md">/);
  const missing = createPageHandler({ installCode: CODE, fetch: fakeFetch({ status: 404 }, []) });
  assert.equal((await missing(new Request('https://orbit.example/none'))).status, 404);
  const custom = createPageHandler({ installCode: CODE, fetch: fakeFetch({ status: 404 }, []),
                                     onNotFound: () => new Response('mine', { status: 404 }) });
  assert.equal(await (await custom(new Request('https://orbit.example/none'))).text(), 'mine');
});

test('ComposedPage and composedMetadata for the App Router', async () => {
  const page = await fetchComposedPage({ installCode: CODE, fetch: fakeFetch(PAGE, []) }, { path: '/pricing' });
  const html = renderToString(React.createElement(ComposedPage, { page }));
  assert.match(html, /data-fb-plan="pl_0123456789"/);
  assert.match(html, /<style>:root\{--ds-color-primary:#123456\}<\/style>/);
  assert.match(html, /fluid-buddha-composed\.global\.js/);
  assert.ok(!html.includes('</script><b>'));
  const meta = composedMetadata(page);
  assert.deepEqual(meta.robots, { index: true, follow: true });
  assert.equal(meta.alternates.canonical, 'https://orbit.example/pricing');
  assert.deepEqual(composedMetadata({ ...page, head: { ...page.head, robots: 'noindex, follow' } }).robots,
    { index: false, follow: true });
  assert.equal(scriptJson({ a: '<&>' }), '{"a":"\\u003c\\u0026\\u003e"}');
  assert.equal(renderToString(React.createElement(ComposedPage, { page: { ...page, notFound: true } })), '');
});
