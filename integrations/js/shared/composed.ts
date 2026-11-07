/**
 * The framework-free core of serving FluidBuddha composed pages (Phase 2) and
 * free-form pages (Phase 4): fetch the page for a path, render the document,
 * and a standard `(Request) => Response` handler. Shared by @fluidbuddha/next
 * and @fluidbuddha/edge; it uses only `fetch`, `Request` and `Response`.
 */
import { parseInstallCode } from './loader';

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
  /** The same page as text for agents (Phase 5), when agent access is on. */
  markdown?: string;
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
  /** True when the page was made for this one visitor (free-form, Phase 4). */
  freeform: boolean;
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
  return { notFound: true, status, html: '', css: '', head: EMPTY_HEAD, data: {}, planId: null, pending: false, freeform: false,
           bundle: null, scripts: null };
}

/** Fetch the composed page for a path on your server. Never throws: on any
 *  failure it answers `notFound` (status 502/504) so you can fall back. */
export async function fetchComposedPage(
  opts: ComposedOptions,
  req: { path: string; searchParams?: SearchParamsLike; headers?: Headers | Record<string, string | undefined>;
         visitor?: string },
): Promise<ComposedPage> {
  const target = parseInstallCode(opts.installCode);
  if (!target) throw new Error('FluidBuddha: invalid install code (expected https://fbk_…@server)');
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
  // The visitor's id (Phase 4): free-form pages are made per person and stay the same
  // for them, so the widget mirrors its visitor id into the first-party `fbvid` cookie.
  const vid = req.visitor || readCookie(cookie, 'fbvid');
  if (vid && VISITOR_RE.test(vid)) url.searchParams.set('visitor', vid);

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
    freeform: !!body.freeform,
    bundle: (body.bundle as ComposedPage['bundle']) || null,
    scripts: (body.scripts as ComposedPage['scripts']) || null,
  };
}

/** JSON that is safe inside a <script> element. */
export function scriptJson(data: unknown): string {
  return JSON.stringify(data).replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026');
}

/** A visitor id FluidBuddha accepts (the widget's `fbvid` cookie). */
export const VISITOR_RE = /^[A-Za-z0-9_-]{8,64}$/;

/** One cookie's value from a Cookie header ('' when absent or malformed). */
export function readCookie(header: string, name: string): string {
  for (const part of (header || '').split(';')) {
    const i = part.indexOf('=');
    if (i > 0 && part.slice(0, i).trim() === name) {
      try { return decodeURIComponent(part.slice(i + 1).trim()); } catch { return ''; }
    }
  }
  return '';
}

export function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

export function httpsOnly(u: string | undefined): string {
  return u && /^https?:\/\//.test(u) ? u : '';
}

/** Metadata for `generateMetadata` (title, description, canonical, robots). */
export function composedMetadata(page: ComposedPage): Record<string, unknown> {
  if (page.notFound) return { robots: { index: false, follow: false } };
  const robots = page.head.robots || '';
  return {
    title: page.head.title,
    description: page.head.description || undefined,
    alternates: page.head.canonical || page.head.markdown ? {
      ...(page.head.canonical ? { canonical: page.head.canonical } : {}),
      ...(httpsOnly(page.head.markdown) ? { types: { 'text/markdown': page.head.markdown } } : {}),
    } : undefined,
    robots: { index: !/noindex/.test(robots), follow: !/nofollow/.test(robots) },
  };
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
    httpsOnly(h.markdown) ? `<link rel="alternate" type="text/markdown" href="${esc(h.markdown!)}">` : '',
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

