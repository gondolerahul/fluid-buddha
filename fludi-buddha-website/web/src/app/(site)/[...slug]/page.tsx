import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ContentPage from "@/components/ContentPage";
import { PAGES, getPage } from "@/content/pages";
import { MEDIA } from "@/content/media";

// Every page is listed in generateStaticParams and prerendered. The route reads its URL before
// rendering so that an unknown path gets a real 404 status (inside <Suspense> it would stream as a
// 200). That makes it a blocking route, which Next.js 16 asks to be declared (docs: instant-navigation).
export const instant = false;

export function generateStaticParams() {
  return PAGES.map((p) => ({ slug: p.path.split("/") }));
}

export async function generateMetadata({ params }: PageProps<"/[...slug]">): Promise<Metadata> {
  const { slug } = await params;
  const page = getPage(slug.join("/"));
  if (!page) return {};
  return { title: page.title, description: page.description, alternates: { canonical: `/${page.path}` }, openGraph: { images: [MEDIA[page.media].src] } };
}

export default async function Page({ params }: PageProps<"/[...slug]">) {
  const { slug } = await params;
  const page = getPage(slug.join("/"));
  if (!page) notFound();
  return <ContentPage page={page} />;
}
