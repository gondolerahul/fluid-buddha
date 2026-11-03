// eslint-config-next 16 ships native flat configs. The previous FlatCompat
// wrapper re-validated them as legacy configs and crashed ("Converting circular
// structure to JSON"), so `npm run lint` never ran (docs/defects.md D-19).
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);
