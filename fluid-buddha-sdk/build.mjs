// Bundles the SDK into three flavours:
//   dist/fluid-buddha.global.js  — IIFE, for a <script> tag (auto-injects)
//   dist/fluid-buddha.mjs        — ESM, for bundlers / `import`
//   dist/fluid-buddha.cjs        — CommonJS
import { build } from 'esbuild';

const shared = {
  entryPoints: ['src/index.ts'],
  bundle: true,
  target: ['es2019'],
  sourcemap: true,
  logLevel: 'info',
};

await Promise.all([
  build({ ...shared, format: 'iife', globalName: 'FluidBuddha', minify: true,
          outfile: 'dist/fluid-buddha.global.js' }),
  build({ ...shared, format: 'esm', outfile: 'dist/fluid-buddha.mjs' }),
  build({ ...shared, format: 'cjs', outfile: 'dist/fluid-buddha.cjs' }),
]);

console.log('built dist/fluid-buddha.{global.js,mjs,cjs}');
