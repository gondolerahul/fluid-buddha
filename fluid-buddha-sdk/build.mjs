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
import { readFile } from 'node:fs/promises';
import path from 'node:path';

// The widget's stylesheet lives in template strings in src/ui/styles.ts, full
// of design notes. esbuild can't minify CSS inside JS strings, so strip the
// comments and collapse whitespace here (no interpolation is used in them).
const minifyCss = {
  name: 'minify-css-strings',
  setup(b) {
    b.onLoad({ filter: /[\\/]ui[\\/]styles\.ts$/ }, async (args) => {
      const src = await readFile(args.path, 'utf8');
      const contents = src.replace(/= `([\s\S]*?)`;/g, (_, css) => '= `' + css
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/\s+/g, ' ')
        .replace(/\s*([{};])\s*/g, '$1')
        // "a: b" → "a:b" (a space after a colon never matters), ", " → ","
        // and the last ";" before "}" — safe in selectors and values alike.
        .replace(/: /g, ':')
        .replace(/\s*,\s*/g, ',')
        .replace(/;}/g, '}')
        .trim() + '`;');
      return { contents, loader: 'ts' };
    });
  },
};

const shared = {
  entryPoints: ['src/index.ts'],
  bundle: true,
  target: ['es2019'],
  sourcemap: true,
  logLevel: 'info',
  plugins: [minifyCss],
};

// For the <script> build, resolve the on-demand loaders (particles, component
// renderers) to their script-tag variants.
const scriptTagLoader = {
  name: 'script-tag-loaders',
  setup(b) {
    b.onResolve({ filter: /\/(particles|components|regions|patch)\/load$|^\.\/load$/ }, (args) => ({
      path: path.join(args.resolveDir, args.path.replace(/load$/, 'load.global.ts')),
    }));
  },
};

await Promise.all([
  build({ ...shared, format: 'iife', globalName: 'FluidBuddha', minify: true,
          plugins: [minifyCss, scriptTagLoader], outfile: 'dist/fluid-buddha.global.js' }),
  build({ ...shared, entryPoints: ['src/ui/particles/global.ts'], format: 'iife',
          globalName: 'FluidBuddhaParticles', minify: true,
          outfile: 'dist/fluid-buddha-particles.global.js' }),
  build({ ...shared, format: 'esm', splitting: true, outdir: 'dist',
          entryNames: 'fluid-buddha', chunkNames: 'chunks/[name]-[hash]',
          outExtension: { '.js': '.mjs' } }),
  build({ ...shared, format: 'cjs', outfile: 'dist/fluid-buddha.cjs' }),
  // The Hindi words, fetched for a Hindi visitor (M2-7).
  build({ ...shared, entryPoints: ['src/i18n/global.ts'], format: 'iife',
          globalName: 'FluidBuddhaHindi', minify: true, outfile: 'dist/fluid-buddha-hi.global.js' }),
  // The component renderers, fetched when a conversation starts (M2-7).
  build({ ...shared, entryPoints: ['src/ui/components/global.ts'], format: 'iife',
          globalName: 'FluidBuddhaComponents', minify: true,
          outfile: 'dist/fluid-buddha-components.global.js' }),
  // Generated regions (Phase 1), fetched when a page has an <fb-region>.
  build({ ...shared, entryPoints: ['src/core/regions/global.ts'], format: 'iife',
          globalName: 'FluidBuddhaRegions', minify: true,
          outfile: 'dist/fluid-buddha-regions.global.js' }),
  // Plan patches (Phase 2), fetched when the agent edits a page on screen.
  build({ ...shared, entryPoints: ['src/core/patch/global.ts'], format: 'iife',
          globalName: 'FluidBuddhaPatcher', minify: true,
          outfile: 'dist/fluid-buddha-patcher.global.js' }),
  // Server-rendered composed pages (Phase 2): hydration + patches.
  build({ ...shared, entryPoints: ['src/composed.ts'], format: 'iife', globalName: 'FluidBuddhaComposed',
          minify: true, outfile: 'dist/fluid-buddha-composed.global.js' }),
  // The recap page's renderer (M2-6): components only, no widget.
  build({ ...shared, entryPoints: ['src/recap.ts'], format: 'iife', globalName: 'FluidBuddhaRecap',
          minify: true, outfile: 'dist/fluid-buddha-recap.global.js' }),
  // The hosted campaign page's script (M3-1): interactive sections + engagement.
  build({ ...shared, entryPoints: ['src/page.ts'], format: 'iife', globalName: 'FluidBuddhaPage',
          minify: true, outfile: 'dist/fluid-buddha-page.global.js' }),
]);

console.log('built dist/fluid-buddha.{global.js,mjs,cjs} + particles + components + regions + hindi + recap + page');
