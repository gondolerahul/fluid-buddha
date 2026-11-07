# @fluidbuddha/edge

Serve FluidBuddha pages from an **edge worker in front of any site** — no framework
needed. For the paths you list, the worker answers with the FluidBuddha page for that
visitor: a composed page, or on free-form routes the visitor's own page. Everything else,
and any path FluidBuddha has no page for, passes through to your origin untouched.

```bash
npm install @fluidbuddha/edge
```

**Cloudflare Workers:**

```ts
import { createEdgeHandler } from '@fluidbuddha/edge';

export default {
  fetch: (req: Request, env: { FLUIDBUDDHA_INSTALL_CODE: string }) =>
    createEdgeHandler({
      installCode: env.FLUIDBUDDHA_INSTALL_CODE,   // https://fbk_…@your-server
      origin: 'https://origin.example.com',        // your site
      routes: ['/pricing', '/products/:slug', '/guides/*'],
    })(req),
};
```

The handler is a plain `(Request) => Promise<Response>`, so it also runs in Vercel or
Netlify edge functions, Deno and Bun.

- `routes` uses the same patterns as the console's **Pages** tab (`:name` is one segment,
  `*` the rest). Leave it out to ask FluidBuddha for every GET path; paths without a
  registered route fall back to the origin.
- **Visitor id.** On a visitor's first request the worker sets a first-party `fbvid`
  cookie (`SameSite=Lax; Secure`, 180 days; `visitorCookieDays` to change, `0` for a
  session cookie). Free-form pages are made per person and stay the same for them; the
  widget reuses the same id. Crawlers get no id and always see the canonical page.
- The visitor's taste (`fbtaste` cookie), UTM tags, search terms, referrer and user agent
  are forwarded, as with `@fluidbuddha/next`.
- Pages are `Cache-Control: private, no-store`. Non-GET requests always go to the origin.
- If FluidBuddha is slow or down, the request falls back to the origin.
