/** The content pages (product, pricing, demo, solutions, legal, …). The header and footer come from the root layout. */
export default function SiteLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <main id="main" className="page">{children}</main>;
}
