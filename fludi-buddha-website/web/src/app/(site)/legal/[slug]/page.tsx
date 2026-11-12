import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { LEGAL } from "@/content/pages";

// Prerendered for every document; an unknown one gets a real 404 (see app/(site)/[...slug]/page.tsx).
export const instant = false;

export function generateStaticParams() {
  return Object.keys(LEGAL).map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps<"/legal/[slug]">): Promise<Metadata> {
  const { slug } = await params;
  return { title: LEGAL[slug]?.title ?? "Legal", alternates: { canonical: `/legal/${slug}` } };
}

export default async function LegalPage({ params }: PageProps<"/legal/[slug]">) {
  const { slug } = await params;
  const doc = LEGAL[slug];
  if (!doc) notFound();
  return (
    <section className="cp-hero plain">
      <div className="wrap" style={{ maxWidth: 820 }}>
        <div className="cp-hero-copy" style={{ maxWidth: "none" }}>
          <h1 className="t-display" style={{ fontSize: "var(--h2)" }}>{doc.title}</h1>
          <div className="prose" style={{ display: "grid", gap: 18 }}>
            <p className="t-lead">The final text of this document is being prepared by our legal team and will be published here before launch.</p>
            <p className="t-body">For questions in the meantime, please <Link href="/contact">contact us</Link>. For how visitor data is handled today, see <Link href="/trust">trust and security</Link>.</p>
          </div>
          <nav aria-label="Legal documents" style={{ display: "flex", flexWrap: "wrap", gap: "10px 20px", paddingTop: 24, borderTop: "1px solid var(--line)" }}>
            {Object.entries(LEGAL).map(([k, v]) => (
              <Link key={k} href={`/legal/${k}`} className="link" aria-current={k === slug ? "page" : undefined}>{v.title}</Link>
            ))}
          </nav>
        </div>
      </div>
    </section>
  );
}
