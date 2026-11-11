import type { Metadata } from "next";
import WorldPage from "@/components/world/WorldPage";
import { WORLDS } from "@/content/worlds";

// A fixed route (not /for/[world]) so that a morph into this world is an instant navigation.
const world = WORLDS.saas;

// One clean, indexable URL per world. Link parameters never create duplicates.
export const metadata: Metadata = {
  title: { absolute: world.meta.title },
  description: world.meta.description,
  alternates: { canonical: world.path },
};

export default function Page() {
  return <WorldPage world={world} />;
}
