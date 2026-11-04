// Bundles the SDK into three flavours:
//   dist/fluid-buddha.global.js  — IIFE, for a <script> tag (auto-injects)
//   dist/fluid-buddha.mjs        — ESM, for bundlers / `import`
//   dist/fluid-buddha.cjs        — CommonJS
//
// Three.js is only needed by Design Level 2 (WS5), so the core stays small:
//   - ESM splits it into dist/chunks/, loaded by a dynamic import;
//   - the IIFE can't split, so it ships as dist/fluid-buddha-particles.global.js,
//     which the core fetches from next to itself (src/ui/particles/load.global.ts);
//   - CJS keeps it inline (Node/bundler consumers that can't split anyway).
import { build } from 'esbuild';
import path from 'node:path';

const shared = {
  entryPoints: ['src/index.ts'],
  bundle: true,
  target: ['es2019'],
  sourcemap: true,
  logLevel: 'info',
};

// For the <script> build, resolve the particle loader to its script-tag variant.
const scriptTagLoader = {
  name: 'script-tag-particles',
  setup(b) {
    b.onResolve({ filter: /\/particles\/load$/ }, (args) => ({
      path: path.join(args.resolveDir, args.path.replace(/load$/, 'load.global.ts')),
    }));
  },
};

await Promise.all([
  build({ ...shared, format: 'iife', globalName: 'FluidBuddha', minify: true,
          plugins: [scriptTagLoader], outfile: 'dist/fluid-buddha.global.js' }),
  build({ ...shared, entryPoints: ['src/ui/particles/global.ts'], format: 'iife',
          globalName: 'FluidBuddhaParticles', minify: true,
          outfile: 'dist/fluid-buddha-particles.global.js' }),
  build({ ...shared, format: 'esm', splitting: true, outdir: 'dist',
          entryNames: 'fluid-buddha', chunkNames: 'chunks/[name]-[hash]',
          outExtension: { '.js': '.mjs' } }),
  build({ ...shared, format: 'cjs', outfile: 'dist/fluid-buddha.cjs' }),
]);

console.log('built dist/fluid-buddha.{global.js,mjs,cjs} + particles');
