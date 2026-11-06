/**
 * @fluidbuddha/next — serve FluidBuddha composed pages from your Next.js site
 * (Phase 2, decision D4).
 *
 * FluidBuddha composes a page for each visitor's goal from your approved
 * components, binds your data, and renders it on its server. This package
 * fetches that page on your server and returns it from your own domain, so
 * search engines get real HTML, a canonical URL and indexing rules.
 *
 *   // app/[...page]/route.ts — the whole page, as a Route Handler
 *   import { createPageHandler } from '@fluidbuddha/next';
 *   export const GET = createPageHandler({ installCode: process.env.FLUIDBUDDHA_INSTALL_CODE! });
 *
 *   // or inside your own layout (App Router, a server component):
 *   import { fetchComposedPage, ComposedPage, composedMetadata } from '@fluidbuddha/next';
 *   export async function generateMetadata({ params, searchParams }) {
 *     return composedMetadata(await fetchComposedPage(opts, { path: '/pricing', searchParams }));
 *   }
 *   export default async function Page({ searchParams }) {
 *     const page = await fetchComposedPage(opts, { path: '/pricing', searchParams });
 *     if (page.notFound) notFound();
 *     return <ComposedPage page={page} />;
 *   }
 *
 * It uses only `fetch`, `Request` and `Response`, so it runs in the Node and
 * Edge runtimes.
 */
import { createElement, Fragment, type ReactElement } from 'react';
import { parseInstallCode } from '../../../shared/loader';

export interface ComposedOptions {
  /** The install code from the console (https://fbk_…@your-server). */
  installCode: string;
  /** Override fetch (tests, custom caching). */
  fetch?: typeof fetch;
  /** Seconds to wait for FluidBuddha before giving up (default 4). */
  timeoutSeconds?: number;
}

export interface ComposedHead {
  title: string;
  description: string;
  canonical: string;
  robots: string;
  json_ld?: Record<string, unknown>;
}

export interface ComposedPage {
  notFound: boolean;
  status: number;
  html: string;
  css: string;
  head: ComposedHead;
  data: Record<string, unknown>;
  planId: string | null;
  pending: boolean;
  bundle: { url: string; integrity: string } | null;
  scripts: { composed: string; loader: string; key: string } | null;
}

const PASS_PARAMS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'q', 'lang', 'persona', 'fbv'];

type SearchParamsLike = URLSearchParams | Record<string, string | string[] | undefined> | undefined;

function getParam(sp: SearchParamsLike, k: string): string | undefined {
  if (!sp) return undefined;
  if (sp instanceof URLSearchParams) return sp.get(k) ?? undefined;
  const v = sp[k];
  return Array.isArray(v) ? v[0] : v;
}

const EMPTY_HEAD: ComposedHead = { title: '', description: '', canonical: '', robots: 'noindex' };

function notFoundPage(status = 404): ComposedPage {
  return { notFound: true, status, html: '', css: '', head: EMPTY_HEAD, data: {}, planId: null, pending: false,
           bundle: null, scripts: null };
}

/** Fetch the composed page for a path on your server. Never throws: on any
 *  failure it answers `notFound` (status 502/504) so you can fall back. */
export async function fetchComposedPage(
  opts: ComposedOptions,
  req: { path: string; searchParams?: SearchParamsLike; headers?: Headers | Record<string, string | undefined> },
): Promise<ComposedPage> {
  const target = parseInstallCode(opts.installCode);
  if (!target) throw new Error('@fluidbuddha/next: invalid install code (expected https://fbk_…@server)');
  const url = new URL(`${target.server}/experience/page`);
  url.searchParams.set('key', target.key);
  url.searchParams.set('path', req.path.startsWith('/') ? req.path : `/${req.path}`);
  for (const k of PASS_PARAMS) {
    const v = getParam(req.searchParams, k);
    if (v) url.searchParams.set(k, v.slice(0, 300));
  }
  const header = (k: string): string | undefined => {
    const h = req.headers;
    if (!h) return undefined;
    return h instanceof Headers ? h.get(k) ?? undefined : h[k] ?? h[k.toLowerCase()];
  };
  const ua = header('user-agent');
  if (ua) url.searchParams.set('ua', ua.slice(0, 300)); // crawlers get the canonical page
  const ref = header('referer');
  if (ref) url.searchParams.set('referrer', ref.slice(0, 500));
  // The visitor's taste (Phase 3): the widget keeps a compact copy in the `fbtaste`
  // cookie on your domain, so the page can be composed for it on the server.
  const cookie = header('cookie') || '';
  const m = /(?:^|;\s*)fbtaste=([^;]*)/.exec(cookie);
  if (m) {
    try { url.searchParams.set('taste', decodeURIComponent(m[1]).slice(0, 200)); } catch { /* malformed */ }
  }

  const doFetch = opts.fetch ?? fetch;
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), (opts.timeoutSeconds ?? 4) * 1000) : null;
  let body: Record<string, unknown>;
  try {
    const res = await doFetch(url.toString(), { headers: { Accept: 'application/json' }, cache: 'no-store',
                                                signal: controller?.signal } as RequestInit);
    if (!res.ok) return notFoundPage(502);
    body = (await res.json()) as Record<string, unknown>;
  } catch {
    return notFoundPage(504);
  } finally {
    if (timer) clearTimeout(timer);
  }
  if (body.status !== 200) return notFoundPage(Number(body.status) || 404);
  return {
    notFound: false,
    status: 200,
    html: String(body.html || ''),
    css: String(body.css || ''),
    head: { ...EMPTY_HEAD, ...(body.head as ComposedHead) },
    data: (body.data as Record<string, unknown>) || {},
    planId: (body.plan_id as string) || null,
    pending: !!body.pending,
    bundle: (body.bundle as ComposedPage['bundle']) || null,
    scripts: (body.scripts as ComposedPage['scripts']) || null,
  };
}

/** JSON that is safe inside a <script> element. */
export function scriptJson(data: unknown): string {
  return JSON.stringify(data).replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026');
}

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function httpsOnly(u: string | undefined): string {
  return u && /^https?:\/\//.test(u) ? u : '';
}

/** Metadata for `generateMetadata` (title, description, canonical, robots). */
export function composedMetadata(page: ComposedPage): Record<string, unknown> {
  if (page.notFound) return { robots: { index: false, follow: false } };
  const robots = page.head.robots || '';
  return {
    title: page.head.title,
    description: page.head.description || undefined,
    alternates: page.head.canonical ? { canonical: page.head.canonical } : undefined,
    robots: { index: !/noindex/.test(robots), follow: !/nofollow/.test(robots) },
  };
}

/** The page body for a server component: styles, the server-rendered HTML,
 *  its data and the scripts that hydrate it and bring the agent. */
export function ComposedPage(props: { page: ComposedPage; withWidget?: boolean }): ReactElement | null {
  const { page, withWidget = true } = props;
  if (page.notFound) return null;
  const s = page.scripts;
  return createElement(Fragment, null,
    createElement('style', { dangerouslySetInnerHTML: { __html: page.css } }),
    page.head.json_ld ? createElement('script', { type: 'application/ld+json',
      dangerouslySetInnerHTML: { __html: scriptJson(page.head.json_ld) } }) : null,
    createElement('div', { dangerouslySetInnerHTML: { __html: page.html } }),
    createElement('script', { type: 'application/json', id: 'fb-page-data',
      dangerouslySetInnerHTML: { __html: scriptJson(page.data) } }),
    httpsOnly(s?.composed) ? createElement('script', { src: s!.composed, defer: true }) : null,
    page.bundle ? createElement('script', { type: 'module', src: page.bundle.url, integrity: page.bundle.integrity,
                                            crossOrigin: 'anonymous' }) : null,
    withWidget && httpsOnly(s?.loader) ? createElement('script', { src: s!.loader, 'data-key': s!.key, async: true })
      : null);
}

/** The full HTML document for a page (what the Route Handler returns). */
export function renderComposedDocument(page: ComposedPage, opts: { lang?: string; withWidget?: boolean } = {}): string {
  const h = page.head;
  const s = page.scripts;
  const meta = [
    `<title>${esc(h.title)}</title>`,
    h.description ? `<meta name="description" content="${esc(h.description)}">` : '',
    h.canonical ? `<link rel="canonical" href="${esc(h.canonical)}">` : '',
    `<meta name="robots" content="${esc(h.robots || 'index, follow')}">`,
    h.json_ld ? `<script type="application/ld+json">${scriptJson(h.json_ld)}</script>` : '',
  ].join('');
  const scripts = [
    httpsOnly(s?.composed) ? `<script src="${esc(s!.composed)}" defer></script>` : '',
    page.bundle ? `<script type="module" src="${esc(page.bundle.url)}" integrity="${esc(page.bundle.integrity)}" crossorigin="anonymous"></script>` : '',
    opts.withWidget !== false && httpsOnly(s?.loader) ? `<script src="${esc(s!.loader)}" data-key="${esc(s!.key)}" async></script>` : '',
  ].join('');
  return `<!doctype html><html lang="${esc(opts.lang || 'en')}"><head><meta charset="utf-8">` +
    `<meta name="viewport" content="width=device-width, initial-scale=1">${meta}<style>${page.css}</style></head>` +
    `<body style="margin:0">${page.html}<script type="application/json" id="fb-page-data">${scriptJson(page.data)}</script>` +
    `${scripts}</body></html>`;
}

/**
 * A catch-all Route Handler (`app/[...page]/route.ts`) that serves composed
 * pages. Paths FluidBuddha has no route for answer `onNotFound` (a 404 page by
 * default), so you can mount it under a prefix or let your own pages win.
 */
export function createPageHandler(
  opts: ComposedOptions & { basePath?: string; onNotFound?: (req: Request) => Response | Promise<Response> },
): (req: Request) => Promise<Response> {
  return async (req: Request) => {
    const url = new URL(req.url);
    let path = url.pathname;
    if (opts.basePath && path.startsWith(opts.basePath)) path = path.slice(opts.basePath.length) || '/';
    const page = await fetchComposedPage(opts, { path, searchParams: url.searchParams, headers: req.headers });
    if (page.notFound) {
      return opts.onNotFound ? opts.onNotFound(req)
        : new Response('<!doctype html><title>Not found</title><p>Not found.</p>',
            { status: page.status === 404 ? 404 : page.status, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    }
    return new Response(renderComposedDocument(page, { lang: url.searchParams.get('lang') === 'hi' ? 'hi' : 'en' }), {
      status: 200,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        // Pages differ per visitor (their goal); never share them in a CDN cache.
        'Cache-Control': 'private, no-store',
        'X-Robots-Tag': page.head.robots || 'index, follow',
        ...(page.planId ? { 'X-FluidBuddha-Plan': page.planId } : {}),
      },
    });
  };
}

export default createPageHandler;
