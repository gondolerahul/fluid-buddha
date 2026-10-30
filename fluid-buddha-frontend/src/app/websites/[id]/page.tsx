"use client";
import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { LoadingScreen } from "@/components/ui";

export default function WebsiteIndex() {
  const params = useParams();
  const router = useRouter();
  useEffect(() => {
    router.replace(`/websites/${params.id}/analytics`);
  }, [params.id, router]);
  return <LoadingScreen />;
}
