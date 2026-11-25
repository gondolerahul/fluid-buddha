// The page the renderer drives: window.render(t) draws the frame at t seconds, and the same t
// always gives the same picture. Open it in a browser with ?t=12.5 to look at one moment, or
// ?play=1 to watch it run.
const q = new URLSearchParams(location.search);
const W = +(q.get('w') || 1280), H = +(q.get('h') || 1024), ss = +(q.get('ss') || 2);
const canvas = document.getElementById('c');
const film = await import('./film.js');
const draw = await film.setup(canvas, { W, H, ss, q });
const gl = canvas.getContext('webgl2');

window.render = (t) => draw(t);

const b64 = async (blob) => {
  const buf = new Uint8Array(await blob.arrayBuffer());
  let s = '';
  for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  return btoa(s);
};
const blobOf = (cv, type, quality) => new Promise((ok) => cv.toBlob(ok, type, quality));

/** One frame as base64: the full frame as PNG, or a smaller JPEG `w` pixels wide for looking at. */
window.__grab = async (t, type = 'image/png', quality, w) => {
  draw(t);
  if (!w || w >= W) return b64(await blobOf(canvas, type, quality));
  const c = document.createElement('canvas'); c.width = w; c.height = Math.round(w * H / W);
  const x = c.getContext('2d'); x.imageSmoothingQuality = 'high'; x.drawImage(canvas, 0, 0, c.width, c.height);
  return b64(await blobOf(c, type, quality));
};

/** A contact sheet: one small frame per time, with its time written on it. */
window.__sheet = async (times, cols = 6, cell = 320) => {
  const ch = Math.round(cell * H / W), rows = Math.ceil(times.length / cols), gap = 6;
  const c = document.createElement('canvas'); c.width = cols * (cell + gap) + gap; c.height = rows * (ch + gap) + gap;
  const x = c.getContext('2d'); x.fillStyle = '#0a0908'; x.fillRect(0, 0, c.width, c.height); x.imageSmoothingQuality = 'high';
  x.font = '600 13px ui-monospace, Consolas, monospace'; x.textBaseline = 'top';
  times.forEach((t, i) => {
    draw(t);
    const px = gap + (i % cols) * (cell + gap), py = gap + Math.floor(i / cols) * (ch + gap);
    x.drawImage(canvas, px, py, cell, ch);
    const label = `${t.toFixed(1)}s  ${(t / window.DUR * 100).toFixed(1)}%` + (window.SHOT_AT ? '  ' + window.SHOT_AT(t) : '');
    x.fillStyle = 'rgba(10,9,8,.72)'; x.fillRect(px, py, x.measureText(label).width + 10, 19);
    x.fillStyle = '#fdc871'; x.fillText(label, px + 5, py + 3);
  });
  return b64(await blobOf(c, 'image/jpeg', .9));
};

/** How long one frame takes, drawn and read back. */
window.__time = (t) => {
  const t0 = performance.now(); draw(t);
  const px = new Uint8Array(4); gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
  return performance.now() - t0;
};

const t0 = +(q.get('t') || 0);
draw(t0);
if (q.get('play')) {
  const start = performance.now() - t0 * 1000, rate = +(q.get('rate') || 1);
  const tick = () => { draw(((performance.now() - start) / 1000 * rate) % window.DUR); requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
}
window.READY = true;
