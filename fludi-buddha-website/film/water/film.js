// The water film: one journey of water, cloud to crystal to ice to water to sea to a vessel.
// TREATMENT.md has the shot list and the reasons. Every frame is painted from strokes, and the
// same t always gives the same picture.
import { init, E, LOOK, dyn } from './stage.js';
import { lerp, seg, sm, ss, key } from './lib.js';
import { drawClouds, cloudsInfo } from './scenes/clouds.js';
import { drawFlake, snowfall, pullBack } from './scenes/flake.js';
import { drawMountains, mountainsInfo } from './scenes/mountains.js';
import { drawGlacier, avalanche, glacierInfo } from './scenes/glacier.js';
import { drawStream, drawRiver, drawSkim, riverInfo } from './scenes/river.js';
import { drawFalls, spray, fallsInfo } from './scenes/falls.js';
import { drawSea, drawUnder, slip, seaInfo } from './scenes/sea.js';
import { screenCam } from './stage.js';
import { drawVessel, vesselInfo } from './scenes/vessel.js';

/** The timeline, in seconds. One place for every cut, so the site's chapters can be set from it. */
export const T = {
  intoCloud: 5.2, vapour: 8.5, crystal: 9.2, grown: 14.6, pull: 16.2, tilt: 19.2, range: 23.4, crane: 25, ridge: 31, avalanche: 30.2, glacier: 31.6, glacierEnd: 40, stream: 39.2, river: 46.2, skim: 51.4, edge: 56, falls: 55.6, sprayFull: 61.4, sea: 61.6, sink: 66.2, under: 67.8, vessel: 71.2, full: 76.2, close: 78.6, rip: 81, back: 84.4, nameAt: 86.2, END: 90,
};

// ------------------------------------------------------------------ shots
const SHOTS = [
  { at: 0, name: 'clouds', draw: (t, tr) => drawClouds(t, { dolly: T.intoCloud + 1.6, end: T.vapour + 1.2, tr }),
    look: () => ({ light: [-.7, -.45, .55], norm: 3.6, lightCol: [1, .93, .8] }) },
  { at: T.vapour, name: 'snow', in: { dur: 1.3, sweep: { c: [.68, .5, 1.6], baked: .6 } },
    draw: (t, tr) => {
      // behind the cloud, once it opens: the open sky the snow falls through, and the tilt down to the range
      const tilt = 1 - sm(seg(t, T.tilt, T.range)), ty = (1 - tilt) * -900;
      if (t > T.pull + .3) drawMountains(t, { tilt, crane: seg(t, T.crane, T.ridge), skyOnly: tilt > .995 });
      drawFlake(t, { t0: T.crystal, grown: T.grown, pull: T.pull, end: T.range, dy: ty, tr });
      if (t > T.pull - .5 && t < T.crane + 2.5) snowfall(t, { back: pullBack(t, T.pull, T.range), fall: (t - T.pull) * 220, amount: seg(t, T.pull - .5, T.pull + 2.5), fade: 1 - sm(seg(t, T.range - 1, T.crane + 2)), ty, tr });
      if (t > T.avalanche) avalanche(t, T.avalanche, { tr });
    },
    look: (t) => { const k = sm(seg(t, T.pull, T.range)); return { light: [lerp(-.5, -.72, k), lerp(-.7, -.5, k), lerp(.6, .5, k)], norm: 3.5, lightCol: [1, lerp(.96, .94, k), lerp(.9, .84, k)] }; } },
  { at: T.glacier, name: 'glacier', in: { dur: 1.6, sweep: { dir: [-.55, .75], off: .69, baked: .7 } },
    draw: (t, tr) => {
      drawGlacier(t, { t0: T.glacier, dur: T.glacierEnd - T.glacier, tr });
      if (t < T.glacier + 3) avalanche(t, T.avalanche);
    },
    look: () => ({ light: [-.62, -.55, .6], norm: 3.6, lightCol: [1, .95, .86] }) },
  { at: T.stream, name: 'stream', in: { dur: 1.4, sweep: { dir: [0, 1.1], baked: .7 } },
    draw: (t, tr) => drawStream(t, { t0: T.stream, dur: T.river + 1 - T.stream, tr }),
    look: () => ({ light: [-.6, -.5, .6], norm: 3.4, lightCol: [1, .94, .84] }) },
  { at: T.river, name: 'river', in: { dur: 1.5, sweep: { c: [.62, .62, 1.6], baked: .7 } },
    draw: (t, tr) => drawRiver(t, { t0: T.river, dur: T.skim - T.river + .6, tr }),
    look: () => ({ light: [-.5, -.62, .6], norm: 3.4, lightCol: [1, .95, .86] }) },
  { at: T.skim, name: 'skim', in: { dur: 1.5, sweep: { dir: [0, -1.2], off: 1.2, baked: .7 } },
    draw: (t, tr) => drawSkim(t, { t0: T.skim, dur: T.edge - T.skim, tr }),
    look: () => ({ light: [-.5, -.6, .6], norm: 3.4, lightCol: [1, .94, .84] }) },
  { at: T.falls, name: 'falls', in: { dur: 1.3, sweep: { dir: [0, 1.1], baked: .6 } },
    draw: (t, tr) => drawFalls(t, { t0: T.falls, dur: T.sprayFull - T.falls, tr }),
    look: () => ({ light: [-.66, -.5, .6], norm: 3.5, lightCol: [1, .94, .84] }) },
  { at: T.sea, name: 'sea', in: { dur: 1.6, sweep: { c: [.62, .45, 1.3], baked: .7 } },
    draw: (t, tr) => {
      const wl = FH0 * (1 - sm(seg(t, T.sink + .3, T.under + .2)));
      const above = () => drawSea(t, { t0: T.sea, dur: T.under - T.sea, sink: seg(t, T.sink, T.under), tr });
      if (t < T.sink + .3) above(); else slip(t, wl, above, () => drawUnder(t, { t0: T.sink, dur: T.END - T.sink }));
      // the spray of the falls drifts off the water as it clears
      if (t < T.sea + 1.8) spray(t, 1 - sm(seg(t, T.sea, T.sea + 1.8)), { cam: screenCam(), n: 600, origin: [640, 1180] });
    },
    look: (t) => { const u = sm(seg(t, T.sink + .3, T.under + .2)); return { light: [-.4, -.7, .6], norm: 3.4, lightCol: [1, .94, .84], expo: lerp(1, 1.04, u) }; } },
  { at: T.vessel, name: 'vessel', in: { dur: 1.4, sweep: { dir: [0, 1.1], baked: .6 } },
    draw: (t, tr) => drawVessel(t, T, tr),
    look: () => ({ light: [-.6, -.6, .6], norm: 3.4, lightCol: [1, .95, .86], vig: .18 }) },
];
export const DUR = T.END;
const FH0 = 1024;

/** Which shot is on screen at t, and how far its transition in has got. */
function at(t) { let i = 0; while (i < SHOTS.length - 1 && t >= SHOTS[i + 1].at) i++; return i; }
window.SHOT_AT = (t) => SHOTS[at(t)].name;

let built = false;
export async function setup(canvas, o) {
  init(canvas, o);
  await document.fonts.load('400 100px "Roblox"').catch(() => {});
  window.DUR = DUR;
  window.GPU = E.renderer();
  return frame;
}

function frame(t) {
  const i = at(t), s = SHOTS[i];
  E.begin(LOOK.ground);
  let look = { ...LOOK, ...(s.look ? s.look(t) : {}) };
  if (s.in && i > 0 && t < s.at + s.in.dur + 2) {
    // a paint-over: the shot before stays under the new one until the knife has covered it
    const prev = SHOTS[i - 1];
    if (t < s.at + s.in.dur) prev.draw(t, {});
    s.draw(t, { appear: s.at, appDur: s.in.appDur ?? .3, sweep: s.in.sweep });
    const k = sm(seg(t, s.at, s.at + s.in.dur)), pl = { ...LOOK, ...(prev.look ? prev.look(t) : {}) };
    look = Object.fromEntries(Object.entries(look).map(([n, v]) => [n, Array.isArray(v) ? v.map((x, j) => lerp(pl[n][j], x, k)) : typeof v === 'number' ? lerp(pl[n], v, k) : v]));
  } else s.draw(t, {});
  dyn.clear();
  E.finish(look);
  if (!built && t > 87) { built = true; window.INFO = `${cloudsInfo()} strokes in the clouds, ${mountainsInfo()} in the range, ${glacierInfo()} in the glacier, ${riverInfo()} in the water, ${fallsInfo()} in the falls, ${seaInfo()} in the sea, ${vesselInfo()} in the room`; }
}
