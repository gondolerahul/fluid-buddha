"use client";
import { useParams } from "next/navigation";
import { useRequireAuth } from "@/lib/auth";
import { AppHeader, WebsiteTabs } from "@/components/Chrome";
import { WebsiteProvider, useWebsite } from "@/components/WebsiteContext";
import { LoadingScreen } from "@/components/ui";

export default function WebsiteLayout({ children }: { children: React.ReactNode }) {
  const auth = useRequireAuth();
  const params = useParams();
  const id = String(params.id);

  if (auth.loading || !auth.tenant) return <LoadingScreen />;

  return (
    <WebsiteProvider id={id}>
      <AppHeader />
      <Header id={id} />
      <main className="content" style={{ margin: "0 auto" }}>{children}</main>
    </WebsiteProvider>
  );
}

function Header({ id }: { id: string }) {
  const { website, notFound } = useWebsite();
  if (notFound) return null;
  return <WebsiteTabs id={id} name={website?.name || "…"} />;
}
