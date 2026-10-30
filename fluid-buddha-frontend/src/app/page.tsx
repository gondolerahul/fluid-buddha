"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { LoadingScreen } from "@/components/ui";

export default function Home() {
  const { tenant, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (loading) return;
    router.replace(tenant ? "/dashboard" : "/login");
  }, [tenant, loading, router]);
  return <LoadingScreen />;
}
