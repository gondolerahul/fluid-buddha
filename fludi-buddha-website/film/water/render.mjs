// Renders the water film (film/water/index.html) frame by frame in headless Chrome.
// No packages: Node's own http server, WebSocket and the Chrome DevTools Protocol.
//
// Run from fludi-buddha-website/:
//   node film/water/render.mjs probe                          # which graphics adapter, how long a frame takes
//   node film/water/render.mjs still 3 12.5 40 [--w 640]      # stills at these seconds -> film/out/water/stills/
//   node film/water/render.mjs sheet 0 110 2 [--cols 8]       # contact sheet: from, to, step (seconds)
//   node film/water/render.mjs frames [--n 540]               # the site's frames, evenly over the film -> film/out/water/frames/
//   node film/water/render.mjs video [--fps 24]               # film/out/water/water.mp4 (needs ffmpeg on the PATH)
// Options: --size 1280x1024 (frame), --ss 2 (supersampling), --q <query passed to the page>, --from/--to (frame range)
import http from 'node:http';
import { spawn } from 'node:child_process';
import { createReadStream, existsSync, mkdirSync, mkdtempSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SITE = path.resolve(HERE, '..', '..');             // fludi-buddha-website/
const OUT = path.join(SITE, 'film', 'out', 'water');

const args = process.argv.slice(2);
const cmd = args.shift();
const opt = {}, pos = [];
for (let i = 0; i < args.length; i++) { if (args[i].startsWith('--')) opt[args[i].slice(2)] = args[i + 1] !== undefined && !args[i + 1].startsWith('--') ? args[++i] : true; else pos.push(args[i]); }
const [W, H] = String(opt.size || '1280x1024').split('x').map(Number);
const SS = Number(opt.ss || 2);

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.ttf': 'font/ttf', '.woff2': 'font/woff2' };

function serve() {
  return new Promise((ok) => {
    const srv = http.createServer((req, res) => {
      const rel = decodeURIComponent(new URL(req.url, 'http://x').pathname);
      const file = path.normalize(path.join(SITE, rel));
      // only the film's sources and the brand's fonts and logos are served
      const allowed = [path.join(SITE, 'film', 'water'), path.join(SITE, 'brand')].some((d) => file.startsWith(d + path.sep));
      if (!allowed || !existsSync(file) || !statSync(file).isFile()) { res.writeHead(404); res.end('not found'); return; }
      res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' });
      createReadStream(file).pipe(res);
    });
    srv.listen(0, '127.0.0.1', () => ok(srv));
  });
}

function findChrome() {
  const c = [process.env.CHROME_PATH, 'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium'].filter(Boolean);
  const hit = c.find((p) => existsSync(p));
  if (!hit) throw new Error('No Chrome or Edge found. Set CHROME_PATH.');
  return hit;
}

async function launch() {
  const profile = mkdtempSync(path.join(tmpdir(), 'fb-water-'));
  const proc = spawn(findChrome(), ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--hide-scrollbars', '--mute-audio', '--enable-gpu', '--ignore-gpu-blocklist', '--use-angle=d3d11', '--enable-unsafe-swiftshader',
    '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--force-device-scale-factor=1', `--window-size=${W},${H}`, 'about:blank'],
  { stdio: ['ignore', 'ignore', 'pipe'] });
  const wsUrl = await new Promise((ok, no) => {
    let buf = '';
    const timer = setTimeout(() => no(new Error('Chrome did not start: ' + buf.slice(0, 400))), 30000);
    proc.stderr.on('data', (d) => { buf += d; const m = buf.match(/DevTools listening on (ws:\/\/\S+)/); if (m) { clearTimeout(timer); ok(m[1]); } });
    proc.on('exit', (c) => no(new Error('Chrome exited early (' + c + '): ' + buf.slice(0, 400))));
  });
  const ws = new WebSocket(wsUrl);
  await new Promise((ok, no) => { ws.onopen = ok; ws.onerror = () => no(new Error('cannot reach Chrome')); });
  let id = 0; const wait = new Map(); const errors = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && wait.has(m.id)) { const [ok, no] = wait.get(m.id); wait.delete(m.id); m.error ? no(new Error(m.error.message)) : ok(m.result); return; }
    if (m.method === 'Runtime.exceptionThrown') { const d = m.params.exceptionDetails; errors.push((d.exception?.description || d.text) + ` (${d.url || ''}:${d.lineNumber})`); }
    if (m.method === 'Runtime.consoleAPICalled') { const text = m.params.args.map((a) => a.value ?? a.description ?? '').join(' '); if (m.params.type === 'error') errors.push(text); else if (opt.verbose || m.params.type === 'warning') console.log('  [page]', text); }
    if (m.method === 'Log.entryAdded' && m.params.entry.level === 'error') errors.push(m.params.entry.text + ' ' + (m.params.entry.url || ''));
  };
  const raw = (method, params = {}, sessionId) => new Promise((ok, no) => { const i = ++id; wait.set(i, [ok, no]); ws.send(JSON.stringify({ id: i, method, params, sessionId })); });
  const { targetInfos } = await raw('Target.getTargets');
  const page = targetInfos.find((t) => t.type === 'page');
  const { sessionId } = await raw('Target.attachToTarget', { targetId: page.targetId, flatten: true });
  const send = (method, params) => raw(method, params, sessionId);
  await send('Page.enable'); await send('Runtime.enable'); await send('Log.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  const evaluate = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  const close = async () => { try { await raw('Browser.close'); } catch { /* already gone */ } proc.kill(); try { rmSync(profile, { recursive: true, force: true }); } catch { /* Chrome may still hold it for a moment */ } };
  return { send, evaluate, errors, close };
}

const pad = (n, w = 5) => String(n).padStart(w, '0');
const fail = (errors) => { if (errors.length) { console.error('Page errors:\n  ' + errors.join('\n  ')); return true; } return false; };

async function main() {
  if (!cmd || !['probe', 'still', 'sheet', 'frames', 'video'].includes(cmd)) { console.log('usage: node film/water/render.mjs probe | still <t...> | sheet <from> <to> <step> | frames | video'); process.exit(1); }
  const srv = await serve();
  const b = await launch();
  let code = 0;
  try {
    const q = `w=${W}&h=${H}&ss=${SS}` + (opt.q ? '&' + opt.q : '');
    const t0 = Date.now();
    await b.send('Page.navigate', { url: `http://127.0.0.1:${srv.address().port}/film/water/index.html?${q}` });
    for (;;) {
      if (fail(b.errors)) throw new Error('the page failed to load');
      if (await b.evaluate('window.READY === true')) break;
      if (Date.now() - t0 > 600000) throw new Error('the page was not ready after 10 minutes');
      await new Promise((r) => setTimeout(r, 250));
    }
    const DUR = await b.evaluate('window.DUR');
    console.log(`ready in ${((Date.now() - t0) / 1000).toFixed(1)} s · ${W}x${H} ss${SS} · film ${DUR.toFixed(2)} s · ${await b.evaluate('window.GPU')}`);
    if (await b.evaluate('!!window.INFO')) console.log('  ' + await b.evaluate('window.INFO'));

    if (cmd === 'probe') {
      const times = (pos.length ? pos.map(Number) : [0, DUR * .25, DUR * .5, DUR * .75]);
      for (const t of times) { const ms = await b.evaluate(`window.__time(${t})`); console.log(`  t=${t.toFixed(2)}  ${ms.toFixed(0)} ms`); }
    } else if (cmd === 'still') {
      const dir = path.join(OUT, 'stills'); mkdirSync(dir, { recursive: true });
      const w = Number(opt.w || 0);
      for (const t of pos.map(Number)) {
        const data = await b.evaluate(`window.__grab(${t}, ${w ? `'image/jpeg', .92, ${w}` : `'image/png'`})`);
        const file = path.join(dir, `${opt.name ? opt.name + '-' : ''}t${t.toFixed(2).replace('.', '_')}.${w ? 'jpg' : 'png'}`);
        writeFileSync(file, Buffer.from(data, 'base64')); console.log('  ' + path.relative(SITE, file));
        if (fail(b.errors)) { code = 1; break; }
      }
    } else if (cmd === 'sheet') {
      const from = Number(pos[0] ?? 0), to = Number(pos[1] ?? DUR), step = Number(pos[2] ?? 2);
      const times = []; for (let t = from; t <= to + 1e-6; t += step) times.push(Math.min(t, DUR));
      const dir = path.join(OUT, 'sheets'); mkdirSync(dir, { recursive: true });
      const data = await b.evaluate(`window.__sheet(${JSON.stringify(times)}, ${Number(opt.cols || 6)}, ${Number(opt.cell || 320)})`);
      const file = path.join(dir, `${opt.name || `sheet-${from}-${to}`}.jpg`);
      writeFileSync(file, Buffer.from(data, 'base64')); console.log('  ' + path.relative(SITE, file));
      if (fail(b.errors)) code = 1;
    } else if (cmd === 'frames') {
      const n = Number(opt.n || 540), dir = path.join(OUT, 'frames'); mkdirSync(dir, { recursive: true });
      const a = Number(opt.from || 0), z = Number(opt.to || n - 1), t1 = Date.now();
      for (let i = a; i <= z; i++) {
        const t = (i / (n - 1)) * DUR;
        writeFileSync(path.join(dir, `f${pad(i + 1)}.png`), Buffer.from(await b.evaluate(`window.__grab(${t}, 'image/png')`), 'base64'));
        if (fail(b.errors)) { code = 1; break; }
        if ((i - a) % 20 === 19 || i === z) { const el = (Date.now() - t1) / 1000, per = el / (i - a + 1); process.stdout.write(`\r  frame ${i + 1}/${n}  ${per.toFixed(2)} s each, ${((z - i) * per / 60).toFixed(1)} min left   `); }
      }
      writeFileSync(path.join(OUT, 'frames.json'), JSON.stringify({ count: n, seconds: DUR, size: [W, H], ss: SS, at: new Date().toISOString() }, null, 2));
      console.log('\n  ' + path.relative(SITE, dir));
    } else if (cmd === 'video') {
      const fps = Number(opt.fps || 24), n = Math.round(DUR * fps), file = path.join(OUT, opt.name || 'water.mp4'); mkdirSync(OUT, { recursive: true });
      const ff = spawn(process.env.FFMPEG || 'ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png', '-i', '-', '-an',
        '-c:v', 'libx264', '-preset', 'slow', '-crf', String(opt.crf || 15), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', file], { stdio: ['pipe', 'inherit', 'inherit'] });
      const done = new Promise((ok, no) => ff.on('exit', (c) => (c ? no(new Error('ffmpeg exit ' + c)) : ok())));
      const t1 = Date.now();
      for (let i = 0; i < n; i++) {
        const buf = Buffer.from(await b.evaluate(`window.__grab(${i / fps}, 'image/png')`), 'base64');
        if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
        if (fail(b.errors)) { code = 1; break; }
        if (i % 24 === 23 || i === n - 1) { const per = (Date.now() - t1) / 1000 / (i + 1); process.stdout.write(`\r  frame ${i + 1}/${n}  ${per.toFixed(2)} s each, ${((n - 1 - i) * per / 60).toFixed(1)} min left   `); }
      }
      ff.stdin.end(); await done;
      console.log('\n  ' + path.relative(SITE, file));
    }
  } catch (e) {
    console.error(String(e.message || e)); fail(b.errors); code = 1;
  } finally {
    await b.close(); srv.close();
  }
  process.exit(code);
}
main();
