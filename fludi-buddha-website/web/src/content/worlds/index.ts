import { DEFAULT_WORLD } from "./default";
import { SAAS_WORLD } from "./saas";
import { EDUCATION_WORLD } from "./education";
import { ENTERPRISE_WORLD } from "./enterprise";
import type { World, WorldId } from "./types";

export const WORLDS: Record<WorldId, World> = {
  default: DEFAULT_WORLD,
  saas: SAAS_WORLD,
  education: EDUCATION_WORLD,
  enterprise: ENTERPRISE_WORLD,
};

/** The worlds that live under /for/<id>. */
export const PERSONA_WORLDS: WorldId[] = ["saas", "education", "enterprise"];

export type { World, WorldId } from "./types";
