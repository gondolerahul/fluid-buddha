// Design Level 2 particle engine — a GPU smoke field (Three.js).
//
// The motion model is a divergence-free **curl-noise** flow (Bridson 2007):
// because the velocity field is the curl of a vector potential it is
// incompressible (mass-conserving), which is exactly what gives real smoke its
// volume-preserving, swirling, never-collapsing look. A buoyancy term biases the
// flow upward (hot smoke rises) and turbulence grows with height (laminar low,
// folding into ribbons up high). The flow displaces each particle around a
// "home" position so the silhouette stays readable while the surface curls.
//
// Formations (home positions):
//   - spread : a continuously-mutating organic blob at screen centre.
//   - bottom : a very shallow band gathered at the screen bottom.
//
// Continuous life (req 1): the centre blob never freezes — it perpetually
// mutates into a NEW member of the same organic family (same rounded silhouette,
// a freshly seeded noise pattern), so it breathes like a living cloud rather than
// cycling through a fixed set of rigid shapes.
//
// Every transition injects a decaying turbulence "burst" so the field BILLOWS
// between formations like a puff of smoke rather than sliding linearly.
//
// Reactivity: `setEnergyProvider` feeds a live 0..1 level (real voice amplitude)
// that scales the flow amplitude — slow and subtle, in sync with speech. Tint
// shifts colour for user vs agent turns.

import * as THREE from 'three';

export type Formation = 'spread' | 'bottom';

export interface ParticleOptions {
  accent?: string;
  count?: number;
}

const FOV = 50;
const CAM_Z = 5.5;
const HOLD_DUR = 0.35;   // brief settle before the blob mutates again (near-continuous)
const MORPH_DUR = 3.4;   // seconds to morph between blob variants / formations (slow, fluid)

function hexToRgb(hex: string): [number, number, number] {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return [0.85, 0.66, 0.23];
  const n = parseInt(m[1], 16);
  return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255];
}

const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;

// ---- CPU organic-blob generator (the centre form) ----
function randSphere(): [number, number, number] {
  const r = Math.cbrt(Math.random());
  const th = Math.random() * Math.PI * 2;
  const ph = Math.acos(2 * Math.random() - 1);
  return [r * Math.sin(ph) * Math.cos(th), r * Math.sin(ph) * Math.sin(th), r * Math.cos(ph)];
}

// Smooth pseudo-noise sampled at a point with a seed offset. Three decorrelated
// trig lobes give an organic, non-repeating field without a full noise table.
function blobNoise(x: number, y: number, z: number, seed: number): number {
  const s = seed;
  return (
    Math.sin(x * 1.7 + y * 0.9 + s) * Math.cos(z * 1.3 + x * 0.5 - s * 0.7) +
    0.5 * Math.sin(y * 2.3 - z * 1.1 + s * 1.7) * Math.cos(x * 1.9 + s * 0.3) +
    0.28 * Math.sin(z * 3.1 + x * 2.0 - s * 1.3)
  ) / 1.78;
}

/** Generate `n` points for ONE organic blob seeded by `seed`. Every seed yields
 *  a sibling of the same rounded, lumpy family — same silhouette character, a
 *  different lobe pattern — so successive blobs read as a single living cloud
 *  mutating, not a slideshow of distinct shapes (req 1). */
function genBlob(seed: number, n: number, out: Float32Array): void {
  for (let i = 0; i < n; i++) {
    let [x, y, z] = randSphere();
    const base = 1.32;
    x *= base; y *= base; z *= base;
    // Two octaves of seeded noise push the surface in/out into soft lobes.
    const a = blobNoise(x * 1.15, y * 1.15, z * 1.15, seed);
    const b = blobNoise(x * 2.6 + 4.0, y * 2.6 + 2.0, z * 2.6 + 6.0, seed * 1.7 + 9.0);
    const disp = a * 0.42 + b * 0.16;
    const r = Math.hypot(x, y, z) || 1e-4;
    x += (x / r) * disp; y += (y / r) * disp; z += (z / r) * disp;
    // Gentle vertical stretch + a soft buoyant taper so it sits like a drifting
    // smoke body rather than a perfect ball.
    y *= 1.12;
    const taper = 1 - 0.12 * Math.max(0, y * 0.5);
    x *= taper; z *= taper;
    out[i * 3] = x;
    out[i * 3 + 1] = y;
    out[i * 3 + 2] = z * 0.72;
  }
}

// ---- GLSL ----
const SIMPLEX = `
vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 permute(vec4 x){return mod289(((x*34.0)+1.0)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1.0/6.0,1.0/3.0); const vec4 D=vec4(0.0,0.5,1.0,2.0);
  vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.0-g; vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+C.yyy; vec3 x3=x0-D.yyy; i=mod289(i);
  vec4 p=permute(permute(permute(i.z+vec4(0.0,i1.z,i2.z,1.0))+i.y+vec4(0.0,i1.y,i2.y,1.0))+i.x+vec4(0.0,i1.x,i2.x,1.0));
  float n_=0.142857142857; vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.0*floor(p*ns.z*ns.z); vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.0*x_);
  vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.0-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.0+1.0; vec4 s1=floor(b1)*2.0+1.0; vec4 sh=-step(h,vec4(0.0));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y); vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
  vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0); m=m*m;
  return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
vec3 snoiseVec3(vec3 x){
  return vec3(snoise(x),
              snoise(vec3(x.y-19.1,x.z+33.4,x.x+47.2)),
              snoise(vec3(x.z+74.2,x.x-124.5,x.y+99.4)));
}
vec3 curlNoise(vec3 p){
  const float e=0.12; vec3 dx=vec3(e,0.0,0.0),dy=vec3(0.0,e,0.0),dz=vec3(0.0,0.0,e);
  vec3 px0=snoiseVec3(p-dx),px1=snoiseVec3(p+dx);
  vec3 py0=snoiseVec3(p-dy),py1=snoiseVec3(p+dy);
  vec3 pz0=snoiseVec3(p-dz),pz1=snoiseVec3(p+dz);
  float x=py1.z-py0.z-pz1.y+pz0.y;
  float y=pz1.x-pz0.x-px1.z+px0.z;
  float z=px1.y-px0.y-py1.x+py0.x;
  return normalize(vec3(x,y,z)*(1.0/(2.0*e)));
}
`;

const VERT = SIMPLEX + `
attribute vec3 aHomeA;
attribute vec3 aHomeB;
attribute vec3 aColor;
attribute float aSize;
attribute float aPhase;
attribute float aSmoke;

uniform float uTime;
uniform float uMorph;
uniform float uEnergy;
uniform float uAmp;
uniform float uBurst;    // transient turbulence during a formation change (req 5)
uniform vec3  uTint;
uniform float uTintMix;

varying vec3 vColor;
varying float vAlpha;

void main(){
  // Staggered home morph (blob↔blob and formation↔formation): each particle
  // crosses the gap at a slightly different time so the change reads as a
  // travelling wave of smoke, not a rigid snap.
  float off = aPhase / 6.2832;
  float t = clamp(uMorph * 1.5 - off * 0.5, 0.0, 1.0);
  t = t*t*(3.0-2.0*t);
  vec3 home = mix(aHomeA, aHomeB, t);

  // Divergence-free smoke flow around the home position. Turbulence scales with
  // height (laminar low, folding high); the sample point drifts downward so the
  // flow SCROLLS UP past the particles (rising smoke). A burst term momentarily
  // amplifies the flow during transitions so movement looks like billowing smoke.
  float h01 = clamp(home.y * 0.42 + 0.5, 0.0, 1.0);
  float turb = 0.34 + h01 * 1.1;
  float burst = 1.0 + uBurst * 1.9;
  float amp = uAmp * aSmoke * turb * burst * (0.5 + uEnergy * 0.95);
  vec3 sp = home * 0.9 + vec3(uTime*0.015, -uTime*0.085, uTime*0.012);
  vec3 flow = curlNoise(sp);
  vec3 flow2 = curlNoise(sp * 2.4 + 11.0) * 0.42;   // finer second octave (ribbon detail)
  vec3 pos = home + (flow + flow2) * amp;
  // Sinuous lateral sway — the S-curve of a rising column, stronger up high.
  pos.x += sin(uTime * 0.5 + home.y * 1.6 + aPhase) * amp * h01 * 0.9;
  pos.z += cos(uTime * 0.42 + home.y * 1.3 + aPhase) * amp * h01 * 0.55;
  // Buoyancy: a soft, slowly varying upward lift (hot smoke rises).
  pos.y += (snoise(home*0.6 + uTime*0.05) * 0.5 + 0.5) * amp * 0.7;

  vec4 mv = modelViewMatrix * vec4(pos, 1.0);
  float camDist = -mv.z;
  gl_PointSize = max(0.6, aSize * (330.0 / max(camDist, 0.1)) * (1.0 + uEnergy*0.35));
  // Depth-cued translucency: nearer puffs read brighter, far ones dissolve —
  // reinforces the volumetric, 3D smoke read.
  vAlpha = smoothstep(11.5, 1.5, camDist);
  vColor = mix(aColor, uTint, uTintMix);
  gl_Position = projectionMatrix * mv;
}
`;

const FRAG = `
varying vec3 vColor;
varying float vAlpha;
void main(){
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;
  float a = smoothstep(0.5, 0.04, d);  // soft, smoky falloff
  gl_FragColor = vec4(vColor, a * vAlpha * 0.7);  // translucent — folds build density
}
`;

export class ParticleField {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private geometry = new THREE.BufferGeometry();
  private material: THREE.ShaderMaterial;
  private clock = new THREE.Clock();
  private raf = 0;
  private running = false;

  private readonly count: number;
  private bottomX: Float32Array;  // -1..1 across the bottom band
  private bottomY: Float32Array;  // 0..1 within the band height
  private zJit: Float32Array;
  private shapeBuf: Float32Array; // scratch: positions for the current blob

  private homeA: THREE.BufferAttribute;
  private homeB: THREE.BufferAttribute;
  private mode: Formation = 'spread';
  private blobSeed = Math.random() * 10;
  private morph = 1;
  private burst = 0;
  private holdTimer = 0;

  private energy = 0;
  private energyTarget = 0;
  private energyProvider?: () => number;
  private tintMix = 0;
  private tintMixTarget = 0;

  constructor(canvas: HTMLCanvasElement, opts: ParticleOptions = {}) {
    const small = typeof window !== 'undefined' && Math.min(window.innerWidth, window.innerHeight) < 700;
    this.count = opts.count ?? (small ? 8000 : 16000);
    const accent = hexToRgb(opts.accent ?? '#d8a93a');

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setClearColor(0x000000, 0);
    this.camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 80);
    this.camera.position.set(0, 0, CAM_Z);

    const n = this.count;
    this.bottomX = new Float32Array(n);
    this.bottomY = new Float32Array(n);
    this.zJit = new Float32Array(n);
    this.shapeBuf = new Float32Array(n * 3);

    const col = new Float32Array(n * 3);
    const size = new Float32Array(n);
    const phase = new Float32Array(n);
    const smoke = new Float32Array(n);
    // Resting smoke is a warm pearl-and-ivory body (luxurious at rest) with
    // gold sparks threaded through the folds; the brand accent is amplified by
    // the agent tint when speaking, cooled to silver when listening.
    const pearl: [number, number, number] = [0.80, 0.78, 0.75];
    const ivory: [number, number, number] = [0.97, 0.95, 0.90];

    for (let i = 0; i < n; i++) {
      this.bottomX[i] = Math.random() * 2 - 1;
      this.bottomY[i] = Math.random();
      this.zJit[i] = (Math.random() - 0.5) * 0.4;

      const roll = Math.random();
      let c: [number, number, number];
      if (roll < 0.55) c = pearl;          // warm pearl smoke (dominant)
      else if (roll < 0.85) c = ivory;     // bright wisps in the folds
      else c = accent;                     // gold spark threaded through
      const j = 0.82 + Math.random() * 0.34;
      col[i * 3] = Math.min(1, c[0] * j);
      col[i * 3 + 1] = Math.min(1, c[1] * j);
      col[i * 3 + 2] = Math.min(1, c[2] * j);

      size[i] = 0.018 + Math.random() * 0.045;
      phase[i] = Math.random() * Math.PI * 2;
      // A spread of wispiness across the body so the surface folds unevenly.
      smoke[i] = 0.3 + Math.random() * 0.5;
    }

    this.homeA = new THREE.BufferAttribute(new Float32Array(n * 3), 3);
    this.homeB = new THREE.BufferAttribute(new Float32Array(n * 3), 3);
    this.geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
    this.geometry.setAttribute('aHomeA', this.homeA);
    this.geometry.setAttribute('aHomeB', this.homeB);
    this.geometry.setAttribute('aColor', new THREE.BufferAttribute(col, 3));
    this.geometry.setAttribute('aSize', new THREE.BufferAttribute(size, 1));
    this.geometry.setAttribute('aPhase', new THREE.BufferAttribute(phase, 1));
    this.geometry.setAttribute('aSmoke', new THREE.BufferAttribute(smoke, 1));

    this.material = new THREE.ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      uniforms: {
        uTime: { value: 0 },
        uMorph: { value: 1 },
        uEnergy: { value: 0 },
        uAmp: { value: 0.28 },        // base flow amplitude — subtle
        uBurst: { value: 0 },
        uTint: { value: new THREE.Vector3(1, 1, 1) },
        uTintMix: { value: 0 },
      },
      transparent: true,
      depthWrite: false,
      blending: THREE.NormalBlending,
    });

    const points = new THREE.Points(this.geometry, this.material);
    points.frustumCulled = false;
    this.scene.add(points);

    this.resize();
    genBlob(this.blobSeed, this.count, this.shapeBuf);
    this.fill(this.homeA.array as Float32Array, 'spread');
    this.fill(this.homeB.array as Float32Array, 'spread');
    this.homeA.needsUpdate = this.homeB.needsUpdate = true;
  }

  private extent(): { hw: number; hh: number } {
    const hh = Math.tan((FOV * Math.PI) / 360) * CAM_Z;
    return { hw: hh * this.camera.aspect, hh };
  }

  /** Write a formation's home positions into `arr` (uses the current shapeBuf for
   *  the spread centre). */
  private fill(arr: Float32Array, mode: Formation): void {
    const { hw, hh } = this.extent();
    if (mode === 'bottom') {
      // A very shallow plume hugging the floor — band height is 10% of the prior
      // band (req 4): 0.01*hh = 0.5% of the full viewport height.
      const bandH = hh * 0.01;
      const baseY = -hh * 0.97;
      for (let i = 0; i < this.count; i++) {
        arr[i * 3] = this.bottomX[i] * hw * 0.98;
        arr[i * 3 + 1] = baseY + this.bottomY[i] * bandH;
        arr[i * 3 + 2] = this.zJit[i];
      }
      return;
    }
    // spread: the organic centre blob fills the whole point set.
    for (let i = 0; i < this.count; i++) {
      arr[i * 3] = this.shapeBuf[i * 3];
      arr[i * 3 + 1] = this.shapeBuf[i * 3 + 1];
      arr[i * 3 + 2] = this.shapeBuf[i * 3 + 2];
    }
  }

  private snapshotInto(arr: Float32Array): void {
    const a = this.homeA.array as Float32Array;
    const b = this.homeB.array as Float32Array;
    const t = this.morph * this.morph * (3 - 2 * this.morph);
    for (let k = 0; k < arr.length; k++) arr[k] = lerp(a[k], b[k], t);
  }

  private startMorphTo(mode: Formation, burst = 1): void {
    this.snapshotInto(this.homeA.array as Float32Array);
    this.fill(this.homeB.array as Float32Array, mode);
    this.homeA.needsUpdate = this.homeB.needsUpdate = true;
    this.morph = 0;
    this.burst = Math.max(this.burst, burst);  // billow on transitions (req 5)
    this.holdTimer = 0;
  }

  // ---- public control ----
  setFormation(mode: Formation): void {
    if (mode === this.mode) return;
    this.mode = mode;
    this.startMorphTo(mode);
  }
  toSpread(): void { this.setFormation('spread'); }
  toBottom(): void { this.setFormation('bottom'); }

  /** Mutate the centre blob into a fresh sibling of the same organic family — a
   *  small seed drift keeps consecutive blobs close so the change reads as a
   *  continuous, breathing mutation rather than a jump (req 1). */
  private mutateBlob(): void {
    this.blobSeed += 0.6 + Math.random() * 0.9;
    genBlob(this.blobSeed, this.count, this.shapeBuf);
    this.startMorphTo('spread', 0.45);  // gentle billow for routine breathing
  }

  /** Provide a live 0..1 energy level (e.g. real voice amplitude) — preferred
   *  over bumpEnergy; scales the smoke flow in sync with speech. */
  setEnergyProvider(fn: () => number): void { this.energyProvider = fn; }
  bumpEnergy(): void { this.energyTarget = 1; }
  setEnergy(v: number): void { this.energyTarget = Math.max(0, Math.min(1, v)); }

  setTint(hex: string, mix = 0.85): void {
    const [r, g, b] = hexToRgb(hex);
    (this.material.uniforms.uTint.value as THREE.Vector3).set(r, g, b);
    this.tintMixTarget = Math.max(0, Math.min(1, mix));
  }
  clearTint(): void { this.tintMixTarget = 0; }

  resize(): void {
    if (typeof window === 'undefined') return;
    const w = window.innerWidth || 800;
    const h = window.innerHeight || 600;
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.fill(this.homeB.array as Float32Array, this.mode);
    this.snapshotInto(this.homeA.array as Float32Array);
    this.homeA.needsUpdate = this.homeB.needsUpdate = true;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.clock.start();
    const loop = () => {
      if (!this.running) return;
      this.raf = requestAnimationFrame(loop);
      this.frame();
    };
    this.raf = requestAnimationFrame(loop);
  }

  stop(): void {
    this.running = false;
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  private frame(): void {
    const dt = Math.min(this.clock.getDelta(), 0.05);
    const t = this.clock.elapsedTime;

    if (this.morph < 1) {
      this.morph = Math.min(1, this.morph + dt / MORPH_DUR);
    } else if (this.mode === 'spread') {
      // Continuous, gentle mutation while idle/listening (req 1).
      this.holdTimer += dt;
      if (this.holdTimer >= HOLD_DUR) this.mutateBlob();
    }
    // Transition turbulence decays back to laminar over ~1.5s.
    this.burst = Math.max(0, this.burst - dt * 0.7);

    // Energy: prefer a live provider (real voice level), else decay model.
    if (this.energyProvider) this.energyTarget = Math.max(0, Math.min(1, this.energyProvider()));
    else this.energyTarget *= 0.95;
    this.energy += (this.energyTarget - this.energy) * 0.1;   // slow, subtle
    this.tintMix += (this.tintMixTarget - this.tintMix) * 0.05;

    const u = this.material.uniforms;
    u.uTime.value = t;
    u.uMorph.value = this.morph;
    u.uEnergy.value = this.energy;
    u.uBurst.value = this.burst * this.burst * (3 - 2 * this.burst); // eased
    u.uTintMix.value = this.tintMix;
    this.renderer.render(this.scene, this.camera);
  }

  dispose(): void {
    this.stop();
    this.geometry.dispose();
    this.material.dispose();
    this.renderer.dispose();
  }
}
