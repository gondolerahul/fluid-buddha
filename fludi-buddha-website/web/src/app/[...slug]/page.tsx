import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ContentPage from "@/components/ContentPage";
import { PAGES, getPage } from "@/content/pages";

export function generateStaticParams() {
  return PAGES.map((p) => ({ slug: p.path.split("/") }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string[] }> }): Promise<Metadata> {
  const { slug } = await params;
  const page = getPage(slug.join("/"));
  if (!page) return {};
  return { title: page.title, description: page.description, openGraph: { images: [`/film/posters/${page.poster}.webp`] } };
}

export default async function Page({ params }: { params: Promise<{ slug: string[] }> }) {
  const { slug } = await params;
  const page = getPage(slug.join("/"));
  if (!page) notFound();
  return <ContentPage page={page} />;
}
