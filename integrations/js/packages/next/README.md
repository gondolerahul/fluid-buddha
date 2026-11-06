# @fluidbuddha/next

Serve FluidBuddha **composed pages** from your Next.js site. FluidBuddha composes each
page for the visitor's goal from your approved components, binds your own data, and
renders it on the server; this package fetches that page on your server and returns it
from your domain, so search engines get real HTML, a canonical URL and indexing rules.

```bash
npm install @fluidbuddha/next
```

**Whole pages, one Route Handler** (`app/[...page]/route.ts`):

```ts
import { createPageHandler } from '@fluidbuddha/next';

export const GET = createPageHandler({
  installCode: process.env.FLUIDBUDDHA_INSTALL_CODE!,   // https://fbk_…@your-server
  // basePath: '/p',             // mount under a prefix
  // onNotFound: () => …,        // paths without a FluidBuddha route
});
```

**Inside your own layout** (App Router server component):

```tsx
import { notFound } from 'next/navigation';
import { ComposedPage, composedMetadata, fetchComposedPage } from '@fluidbuddha/next';

const opts = { installCode: process.env.FLUIDBUDDHA_INSTALL_CODE! };

export async function generateMetadata({ searchParams }) {
  return composedMetadata(await fetchComposedPage(opts, { path: '/pricing', searchParams: await searchParams }));
}

export default async function Pricing({ searchParams }) {
  const page = await fetchComposedPage(opts, { path: '/pricing', searchParams: await searchParams });
  if (page.notFound) notFound();
  return <ComposedPage page={page} />;
}
```

- Register the route (`/pricing`, `/products/:slug`, `/guides/*`) in the console's
  **Pages** tab; pick a canonical page for search engines there.
- The visitor's UTM tags, search terms, referrer and user agent are passed on, so the page
  fits their goal and crawlers get the canonical page. Their taste travels in the widget's
  `fbtaste` session cookie on your domain and is forwarded too.
- Responses are `Cache-Control: private, no-store`: pages differ per visitor.
- `fetchComposedPage` never throws on network or server errors; it answers `notFound`
  (status 502/504), so your own page can render instead.
- Runs in the Node and Edge runtimes (`fetch`, `Request`, `Response` only).
