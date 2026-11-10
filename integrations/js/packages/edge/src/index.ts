/**
 * @fluidbuddha/edge — serve FluidBuddha pages from an edge worker in front of
 * any site (Phase 4, decision D4: "Next.js first, then edge").
 *
 * The worker sits between visitors and your origin. For the paths you list it
 * answers with the FluidBuddha page for that visitor (a composed page, or on
 * free-form routes the visitor's own page); everything else — and any path
 * FluidBuddha has no page for — passes through to your origin untouched.
 *
 *   // Cloudflare Workers
 *   import { createEdgeHandler } from '@fluidbuddha/edge';
 *   export default {
 *     fetch: (req, env) => createEdgeHandler({
 *       installCode: env.FLUIDBUDDHA_INSTALL_CODE,
 *       origin: 'https://origin.example.com',
 *       routes: ['/pricing', '/products/:slug', '/guides/*'],
 *     })(req),
 *   };
 *
 * It uses only `fetch`, `Request`, `Response` and `crypto`, so it runs on any
 * runtime with the web platform APIs.
 */
import {
  createPageHandler, readCookie, VISITOR_RE, type ComposedOptions,
} from '../../../shared/composed';

export interface EdgeOptions extends ComposedOptions {
  /** Where everything else goes: your site's origin (https://origin.example.com). */
  origin: string;
  /** Path patterns FluidBuddha answers (`/pricing`, `/products/:slug`, `/guides/*`).
   *  Leave out to try every GET path (FluidBuddha answers only its registered routes). */
  routes?: string[];
  /** Days the `fbvid` visitor cookie lasts (default 180; 0 = a session cookie). */
  visitorCookieDays?: number;
}

/** Does a path match a pattern (`:name` one segment, `*` the rest)? */
export function matchRoute(pattern: string, path: string): boolean {
  const p = pattern.split('/').filter(Boolean);
  const s = path.replace(/\/+$/, '').split('/').filter(Boolean);
  for (let i = 0; i < p.length; i++) {
    if (p[i] === '*') return true;
    if (i >= s.length) return false;
    if (!p[i].startsWith(':') && p[i] !== s[i].toLowerCase()) return false;
  }
  return p.length === s.length;
}

function newVisitorId(): string {
  const c = (globalThis as { crypto?: Crypto }).crypto;
  if (c?.randomUUID) return c.randomUUID().replace(/-/g, '');
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join('');
}

const BOT = /bot|crawl|spider|slurp|bingpreview|facebookexternalhit|embedly|quora link preview|whatsapp|telegrambot/i;

/** The edge handler: `(Request) => Promise<Response>`. */
export function createEdgeHandler(opts: EdgeOptions): (req: Request) => Promise<Response> {
  const origin = new URL(opts.origin);
  const doFetch = opts.fetch ?? fetch;
  const days = opts.visitorCookieDays ?? 180;
  const page = createPageHandler({ ...opts, onNotFound: (req) => passThrough(req) });

  function passThrough(req: Request): Promise<Response> {
    const u = new URL(req.url);
    const target = new URL(u.pathname + u.search, origin);
    return doFetch(new Request(target.toString(), req));
  }

  return async (req: Request) => {
    const url = new URL(req.url);
    const wanted = (req.method === 'GET' || req.method === 'HEAD')
      && (!opts.routes || opts.routes.some((r) => matchRoute(r, url.pathname)));
    // A stable id per visitor, so a free-form page stays the same for them. Minted
    // here on the first visit (crawlers get none); the widget reuses the same cookie.
    const cookie = req.headers.get('cookie') || '';
    let vid = readCookie(cookie, 'fbvid');
    let minted = '';
    if (!VISITOR_RE.test(vid) && !BOT.test(req.headers.get('user-agent') || '')) {
      vid = minted = newVisitorId();
    }
    let res: Response;
    if (!wanted) {
      res = await passThrough(req);
    } else {
      const headers = new Headers(req.headers);
      if (minted) headers.set('cookie', (cookie ? `${cookie}; ` : '') + `fbvid=${minted}`);
      res = await page(new Request(req.url, { method: 'GET', headers }));
      if (req.method === 'HEAD') res = new Response(null, res);
    }
    if (!minted) return res;
    const out = new Response(res.body, res); // headers of a fetched response are immutable
    out.headers.append('Set-Cookie', `fbvid=${minted}; Path=/; SameSite=Lax; Secure` +
      (days > 0 ? `; Max-Age=${days * 86400}` : ''));
    return out;
  };
}

export { fetchComposedPage, renderComposedDocument, readCookie } from '../../../shared/composed';
export type { ComposedOptions, ComposedPage, ComposedHead } from '../../../shared/composed';
export default createEdgeHandler;
