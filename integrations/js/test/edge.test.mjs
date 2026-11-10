// @fluidbuddha/edge: compose registered routes, pass the rest to the origin, mint fbvid (Phase 4).
import test from 'node:test';
import assert from 'node:assert/strict';

const { createEdgeHandler, matchRoute } = await import('../packages/edge/dist/index.mjs');
const next = await import('../packages/next/dist/index.mjs');

const CODE = 'https://fbk_abcdefgh12345678@agent.example.com';
const PAGE = {
  status: 200, plan_id: 'pl_0123456789', pending: false, freeform: true,
  html: '<main class="fbpage-root"><section data-fb-region="hero"><h1>For you</h1></section></main>',
  css: '', head: { title: 'Plans', description: '', canonical: '', robots: 'noindex, follow' },
  data: { plan_id: 'pl_0123456789' }, scripts: null,
};

function fakeFetch(calls, { page = PAGE } = {}) {
  return async (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    calls.push({ url, input, init });
    if (url.startsWith('https://agent.example.com/')) return new Response(JSON.stringify(page), { status: 200 });
    return new Response(`origin:${new URL(url).pathname}`, { status: 200, headers: { 'X-Origin': '1' } });
  };
}

test('route patterns', () => {
  assert.ok(matchRoute('/pricing', '/pricing') && matchRoute('/pricing', '/pricing/'));
  assert.ok(matchRoute('/products/:slug', '/products/orbit') && !matchRoute('/products/:slug', '/products'));
  assert.ok(matchRoute('/guides/*', '/guides/a/b') && !matchRoute('/pricing', '/pricing/x'));
  assert.ok(matchRoute('/', '/') && !matchRoute('/', '/x'));
});

test('registered routes are composed with a new visitor id; the rest passes through', async () => {
  const calls = [];
  const h = createEdgeHandler({ installCode: CODE, origin: 'https://origin.example.com', fetch: fakeFetch(calls),
                                routes: ['/pricing'] });
  const res = await h(new Request('https://orbit.example/pricing?utm_source=x', { headers: { 'user-agent': 'Mozilla' } }));
  assert.equal(res.status, 200);
  assert.match(await res.text(), /For you/);
  const vid = /fbvid=([a-f0-9]{32})/.exec(res.headers.get('set-cookie'))[1];
  assert.match(res.headers.get('set-cookie'), /SameSite=Lax; Secure; Max-Age=15552000/);
  assert.equal(new URL(calls[0].url).searchParams.get('visitor'), vid, 'the minted id reaches FluidBuddha');

  const other = await h(new Request('https://orbit.example/about?x=1', { headers: { cookie: 'fbvid=visitor-0001abc' } }));
  assert.equal(await other.text(), 'origin:/about');
  assert.equal(other.headers.get('x-origin'), '1');
  assert.equal(other.headers.get('set-cookie'), null, 'an existing id is kept');
  assert.equal(calls.at(-1).url, 'https://origin.example.com/about?x=1');

  const post = await h(new Request('https://orbit.example/pricing', { method: 'POST', body: 'a=1',
                                                                     headers: { cookie: 'fbvid=visitor-0001abc' } }));
  assert.equal(await post.text(), 'origin:/pricing');
});

test('paths FluidBuddha has no page for fall back to the origin; crawlers get no id', async () => {
  const calls = [];
  const h = createEdgeHandler({ installCode: CODE, origin: 'https://origin.example.com',
                                fetch: fakeFetch(calls, { page: { status: 404 } }) });
  const res = await h(new Request('https://orbit.example/blog/post', { headers: { 'user-agent': 'Googlebot/2.1' } }));
  assert.equal(await res.text(), 'origin:/blog/post');
  assert.equal(res.headers.get('set-cookie'), null);
  assert.equal(new URL(calls[0].url).searchParams.get('visitor'), null);
});

test('the Next adapter forwards fbvid and reports free-form pages', async () => {
  const calls = [];
  const page = await next.fetchComposedPage({ installCode: CODE, fetch: fakeFetch(calls) },
    { path: '/pricing', headers: { cookie: 'a=1; fbvid=visitor-0001abc' } });
  assert.equal(new URL(calls[0].url).searchParams.get('visitor'), 'visitor-0001abc');
  assert.equal(page.freeform, true);
  await next.fetchComposedPage({ installCode: CODE, fetch: fakeFetch(calls) },
    { path: '/pricing', headers: { cookie: 'fbvid=<bad>' } });
  assert.equal(new URL(calls.at(-1).url).searchParams.get('visitor'), null, 'malformed ids are dropped');
});
