// Builds @fluidbuddha/react and @fluidbuddha/vue: ESM + CJS with the shared
// loader bundled in (the framework itself stays external), then type
// declarations from tsc.
import { build } from 'esbuild';
import { execFileSync } from 'node:child_process';
import { rmSync } from 'node:fs';
import path from 'node:path';

const packages = { react: ['react', 'react/jsx-runtime'], vue: ['vue'] };

for (const [name, external] of Object.entries(packages)) {
  const dir = path.join('packages', name);
  rmSync(path.join(dir, 'dist'), { recursive: true, force: true });
  const shared = {
    entryPoints: [path.join(dir, 'src/index.ts')],
    bundle: true,
    external,
    target: ['es2019'],
    sourcemap: true,
    logLevel: 'info',
  };
  await build({ ...shared, format: 'esm', outfile: path.join(dir, 'dist/index.mjs') });
  await build({ ...shared, format: 'cjs', outfile: path.join(dir, 'dist/index.cjs') });
  execFileSync(process.execPath, [
    path.join('node_modules', 'typescript', 'bin', 'tsc'),
    '-p', path.join(dir, 'tsconfig.json'), '--emitDeclarationOnly', '--outDir', path.join(dir, 'dist/types'),
  ], { stdio: 'inherit' });
}
console.log('built @fluidbuddha/react and @fluidbuddha/vue');
