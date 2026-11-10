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
import { httpsOnly, scriptJson, type ComposedPage as PageData } from '../../../shared/composed';

export {
  composedMetadata, createPageHandler, fetchComposedPage, readCookie, renderComposedDocument, scriptJson,
} from '../../../shared/composed';
export type { ComposedHead, ComposedOptions } from '../../../shared/composed';

/** A fetched page (the same name as the component that renders it). */
export interface ComposedPage extends PageData {}

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

export { createPageHandler as default } from '../../../shared/composed';
