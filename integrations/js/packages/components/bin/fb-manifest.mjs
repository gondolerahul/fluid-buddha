#!/usr/bin/env node
// Build a FluidBuddha component manifest from your component definitions.
//
//   fb-manifest --module ./dist/fb-components.js \
//               --bundle-file ./dist/fb-components.js \
//               --bundle-url https://cdn.example.com/fb-components.js \
//               [--out manifest.json] [--no-defaults]
//
// --module       an ES module whose exports include defineFbComponent(...)
//                results (any export that has {id, tag, entry}).
// --bundle-file  the built script you will host; its sha384 integrity hash is
//                computed here, so the manifest pins exactly that file.
// --bundle-url   where that file will be served from (https).
//
// Paste the output into the console (Components → New draft) or point
// <SITE>_COMPONENT_MANIFEST at it.
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

export function sriHash(bytes) {
  return 'sha384-' + createHash('sha384').update(bytes).digest('base64');
}

export function collectDefinitions(mod) {
  const defs = [];
  const visit = (v) => {
    if (Array.isArray(v)) v.forEach(visit);
    else if (v && typeof v === 'object' && typeof v.id === 'string' && typeof v.tag === 'string' && v.entry) defs.push(v);
  };
  Object.values(mod).forEach(visit);
  return defs;
}

function arg(argv, name) {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : undefined;
}

export async function main(argv = process.argv.slice(2)) {
  const modPath = arg(argv, '--module');
  const bundleFile = arg(argv, '--bundle-file');
  const bundleUrl = arg(argv, '--bundle-url');
  const out = arg(argv, '--out');
  if (!modPath) throw new Error('--module is required');
  if ((bundleFile && !bundleUrl) || (!bundleFile && bundleUrl)) {
    throw new Error('--bundle-file and --bundle-url go together');
  }
  if (bundleUrl && !bundleUrl.startsWith('https://')) throw new Error('--bundle-url must be https');
  const mod = await import(pathToFileURL(path.resolve(modPath)).href);
  const defs = collectDefinitions(mod);
  if (!defs.length) throw new Error(`No defineFbComponent(...) exports found in ${modPath}`);
  const seen = new Set();
  for (const d of defs) {
    if (seen.has(d.id)) throw new Error(`Duplicate component id ${d.id}`);
    seen.add(d.id);
  }
  const manifest = { include_defaults: !argv.includes('--no-defaults'), components: defs.map((d) => d.entry) };
  if (bundleFile) manifest.bundle = { url: bundleUrl, integrity: sriHash(readFileSync(bundleFile)) };
  const json = JSON.stringify(manifest, null, 2) + '\n';
  if (out) writeFileSync(out, json);
  else process.stdout.write(json);
  return manifest;
}

const invoked = process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url;
if (invoked) {
  main().catch((err) => {
    process.stderr.write(`fb-manifest: ${err.message}\n`);
    process.exit(1);
  });
}
