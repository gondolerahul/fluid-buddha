import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { LEGAL } from "@/content/pages";

export function generateStaticParams() {
  return Object.keys(LEGAL).map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  return { title: LEGAL[slug]?.title ?? "Legal" };
}

export default async function LegalPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const doc = LEGAL[slug];
  if (!doc) notFound();
  return (
    <section className="section" style={{ paddingTop: 200 }}>
      <div className="wrap stack-5" style={{ maxWidth: 760 }}>
        <div className="eyebrow">Legal</div>
        <h1 className="h1">{doc.title}</h1>
        <p className="lead">
          The final text of this document is being prepared by our legal team and will be published here before launch.
          For questions in the meantime, please <Link href="/contact" style={{ color: "var(--accent)" }}>contact us</Link>.
        </p>
        <p className="illustrative">FluidBuddha · a Buddha Cognitive Lab product</p>
      </div>
    </section>
  );
}
