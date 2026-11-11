import type { Metadata } from "next";
import WorldPage from "@/components/world/WorldPage";
import { WORLDS } from "@/content/worlds";

const world = WORLDS.default;

export const metadata: Metadata = {
  title: { absolute: world.meta.title },
  description: world.meta.description,
  alternates: { canonical: "/" },
};

/** World 0: the default site, shown when we do not know who the visitor is. */
export default function DefaultWorld() {
  return <WorldPage world={world} />;
}
