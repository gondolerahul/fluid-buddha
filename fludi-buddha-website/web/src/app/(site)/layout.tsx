import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import AskBar from "@/components/AskBar";

/** Chrome for the earlier content pages (pricing, demo, industries, legal). The four worlds have their own. */
export default function SiteLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <Nav />
      <main id="main">{children}</main>
      <Footer />
      <AskBar />
    </>
  );
}
