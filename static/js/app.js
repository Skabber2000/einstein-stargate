import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const C = 2.99792458e8;
const G = 6.67430e-11;
const HBAR = 1.054571817e-34;
const M_SUN = 1.98892e30;
const M_JUP = 1.898e27;
const R_SUN = 6.96e8;
const WORLD_E_PER_YEAR = 6.0e20;            // ~6 ×10²⁰ J / yr  (BP-stat-2024-ish)

const fmt = (x, d = 3) => {
  if (!isFinite(x)) return '∞';
  if (x === 0) return '0';
  const e = Math.floor(Math.log10(Math.abs(x)));
  if (e >= -2 && e <= 3) return x.toFixed(Math.max(0, d - e));
  const m = x / 10 ** e;
  return `${m.toFixed(d - 1)}×10${supr(e)}`;
};
const supr = (n) => {
  const map = { '-': '⁻', '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹' };
  return [...String(n)].map((c) => map[c] || c).join('');
};
const $ = (id) => document.getElementById(id);

// ─────────── Scenes ───────────
const SCENES = [
  {
    key: 'moon', name: 'Moon',
    M: 7.342e22, R: 1.7374e6,
    title: 'A Moon barely dents spacetime',
    body: 'The Moon\'s Schwarzschild radius is 0.11 mm — smaller than a grain of sand. The "well" you see is what an ant on the surface feels: 1.6 m/s² and a curvature too small to measure.',
  },
  {
    key: 'earth', name: 'Earth',
    M: 5.9722e24, R: 6.371e6,
    title: 'Earth: a dimple in the fabric',
    body: 'r_s = 8.95 mm. We orbit the Sun and feel "gravity" — but the geometric distortion is 1 part in 10⁹. Newton is a fantastic approximation.',
  },
  {
    key: 'sun', name: 'Sun',
    M: 1.989e30, R: R_SUN,
    title: 'The Sun: still 99.9996% flat',
    body: 'r_s = 2.95 km, R = 696 000 km. Curvature at the Sun\'s surface deflects starlight by 1.75″ (the Eddington 1919 measurement). The well looks deep only because we\'re plotting in r_s units.',
  },
  {
    key: 'r136',
    name: 'R136a1',
    M: 4.0e32, R: 31 * R_SUN,   // ~200 M☉, ~30 R☉
    title: 'R136a1 — the heaviest known star',
    body: '≈200 M☉ in the Tarantula Nebula. r_s ≈ 590 km. Despite being the most massive star ever weighed, the gravitational distortion at its surface is still only 8 ×10⁻⁵ — stars cannot break spacetime by mass alone.',
  },
  {
    key: 'bh', name: '10 M☉ black hole',
    M: 10 * M_SUN, R: 10 * 2 * G * M_SUN / (C * C),  // R = rs
    title: 'Black hole: spacetime closes on itself',
    body: 'r_s = 29.5 km. Inside the event horizon, time and radius swap roles. The full Flamm paraboloid is exposed — this is what "spacetime pressed past its breaking point" looks like. But there is only one mouth.',
  },
  {
    key: 'gate', name: 'Star-Gate', wormhole: true,
    M: 0, R: 0, b0: 2.0,        // 2 m throat — wide enough to walk through
    title: 'Star-Gate: spacetime torn open from both sides',
    body: 'Two Schwarzschild geometries glued at a throat = Einstein-Rosen bridge. A black hole has one mouth; a traversable wormhole has two. The cost: hold the throat open against gravity\'s urge to collapse it — which means exotic, negative-energy matter.',
  },
];

let scene_i = 0;

// ─────────── Three.js ───────────
const host = $('three');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0e18);

const camera = new THREE.PerspectiveCamera(46, 1, 0.05, 5000);
camera.position.set(0, 4.5, 12);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.outputColorSpace = THREE.SRGBColorSpace;
host.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.set(0, -1.5, 0);
controls.minDistance = 4;
controls.maxDistance = 40;

scene.add(new THREE.AmbientLight(0xffffff, 1.0));

// Stars
{
  const g = new THREE.BufferGeometry();
  const n = 1400, p = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const r = 60 + Math.random() * 40;
    const t = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    p[i*3]   = r * Math.sin(phi) * Math.cos(t);
    p[i*3+1] = r * Math.cos(phi);
    p[i*3+2] = r * Math.sin(phi) * Math.sin(t);
  }
  g.setAttribute('position', new THREE.BufferAttribute(p, 3));
  scene.add(new THREE.Points(g, new THREE.PointsMaterial({ size: 0.18, color: 0x7c89ab, transparent: true, opacity: 0.7 })));
}

// ─────────── Geometry ───────────
// Scene-units convention: r_s_scene = 0.6. The radial extent of the visible bowl is r ∈ [r_inner, R_MAX].
// r_inner = max(rs, body_surface) mapped from physical compactness x = R/rs (log scale).
const RS_SCENE = 0.6, R_MAX_SCENE = 6.0;
const N_R = 132, N_T = 144;

let flammGrid, bodyMesh, bodyHalo, horizonRing, wormhole;

function makeFlammWireGeometry(innerScene) {
  // Build a wireframe grid: concentric circles (constant r) + radial spokes (constant θ).
  const verts = [];
  const NR_circles = 20;      // radial divisions
  const NT_circle  = 96;      // tessellation of each circle
  const NT_spokes  = 36;      // number of spokes
  const NR_spoke   = 48;      // segments per spoke

  // Concentric circles
  for (let i = 0; i < NR_circles; i++) {
    const u = i / (NR_circles - 1);
    const r = innerScene + (R_MAX_SCENE - innerScene) * (u * u);
    const z = 2 * Math.sqrt(RS_SCENE * Math.max(0, r - RS_SCENE));
    for (let j = 0; j < NT_circle; j++) {
      const t1 = (j     / NT_circle) * Math.PI * 2;
      const t2 = ((j+1) / NT_circle) * Math.PI * 2;
      verts.push(r * Math.cos(t1), -z, r * Math.sin(t1));
      verts.push(r * Math.cos(t2), -z, r * Math.sin(t2));
    }
  }
  // Radial spokes
  for (let j = 0; j < NT_spokes; j++) {
    const t = (j / NT_spokes) * Math.PI * 2;
    for (let i = 0; i < NR_spoke; i++) {
      const u1 = i / NR_spoke;
      const u2 = (i+1) / NR_spoke;
      const r1 = innerScene + (R_MAX_SCENE - innerScene) * (u1 * u1);
      const r2 = innerScene + (R_MAX_SCENE - innerScene) * (u2 * u2);
      const z1 = 2 * Math.sqrt(RS_SCENE * Math.max(0, r1 - RS_SCENE));
      const z2 = 2 * Math.sqrt(RS_SCENE * Math.max(0, r2 - RS_SCENE));
      verts.push(r1 * Math.cos(t), -z1, r1 * Math.sin(t));
      verts.push(r2 * Math.cos(t), -z2, r2 * Math.sin(t));
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(verts), 3));
  return geo;
}

// soft glow sprite (additive)
function makeGlowSprite(color, size) {
  const canv = document.createElement('canvas');
  canv.width = canv.height = 256;
  const g = canv.getContext('2d');
  const grd = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  grd.addColorStop(0.0, color + 'ff');
  grd.addColorStop(0.4, color + '66');
  grd.addColorStop(1.0, color + '00');
  g.fillStyle = grd;
  g.fillRect(0, 0, 256, 256);
  const tex = new THREE.CanvasTexture(canv);
  const mat = new THREE.SpriteMaterial({ map: tex, color: 0xffffff, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(size, size, 1);
  return sprite;
}

function makeWormholeWireGeometry() {
  // Einstein-Rosen bridge in wireframe — two Flamm paraboloids mirrored about z=0.
  const verts = [];
  const NR_circles = 20, NT_circle = 96, NT_spokes = 36, NR_spoke = 48;
  for (const sign of [-1, +1]) {
    // circles
    for (let i = 0; i < NR_circles; i++) {
      const u = i / (NR_circles - 1);
      const r = RS_SCENE + (R_MAX_SCENE - RS_SCENE) * (u * u);
      const z = 2 * Math.sqrt(RS_SCENE * (r - RS_SCENE));
      for (let j = 0; j < NT_circle; j++) {
        const t1 = (j     / NT_circle) * Math.PI * 2;
        const t2 = ((j+1) / NT_circle) * Math.PI * 2;
        verts.push(r * Math.cos(t1), sign * z, r * Math.sin(t1));
        verts.push(r * Math.cos(t2), sign * z, r * Math.sin(t2));
      }
    }
    // spokes
    for (let j = 0; j < NT_spokes; j++) {
      const t = (j / NT_spokes) * Math.PI * 2;
      for (let i = 0; i < NR_spoke; i++) {
        const u1 = i / NR_spoke, u2 = (i+1) / NR_spoke;
        const r1 = RS_SCENE + (R_MAX_SCENE - RS_SCENE) * (u1 * u1);
        const r2 = RS_SCENE + (R_MAX_SCENE - RS_SCENE) * (u2 * u2);
        const z1 = 2 * Math.sqrt(RS_SCENE * (r1 - RS_SCENE));
        const z2 = 2 * Math.sqrt(RS_SCENE * (r2 - RS_SCENE));
        verts.push(r1 * Math.cos(t), sign * z1, r1 * Math.sin(t));
        verts.push(r2 * Math.cos(t), sign * z2, r2 * Math.sin(t));
      }
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(verts), 3));
  return geo;
}

function clearGeometry() {
  for (const m of [flammGrid, bodyMesh, bodyHalo, horizonRing, wormhole]) {
    if (m) { scene.remove(m); m.geometry?.dispose(); m.material?.dispose?.(); }
  }
  flammGrid = bodyMesh = bodyHalo = horizonRing = wormhole = null;
}

// Per-scene body colours
const BODY_STYLE = {
  moon:  { core: 0xc6cad2, glow: '#c8cbd3' },
  earth: { core: 0x4f9bff, glow: '#4f9bff' },
  sun:   { core: 0xffc24a, glow: '#ffb45a' },
  r136:  { core: 0xb5c8ff, glow: '#9cb5ff' },     // blue supergiant
  bh:    { core: 0x000000, glow: '#ff5b8a' },     // black core, pink rim
};

function buildScene(s) {
  clearGeometry();
  if (s.wormhole) {
    wormhole = new THREE.LineSegments(
      makeWormholeWireGeometry(),
      new THREE.LineBasicMaterial({ color: 0xe7ecf5, transparent: true, opacity: 0.55 })
    );
    scene.add(wormhole);
    horizonRing = new THREE.Mesh(
      new THREE.TorusGeometry(RS_SCENE, 0.028, 16, 144),
      new THREE.MeshBasicMaterial({ color: 0xff5b8a })
    );
    horizonRing.rotation.x = Math.PI / 2;
    scene.add(horizonRing);
    // tiny halo at throat to suggest exotic energy
    bodyHalo = makeGlowSprite('#ff5b8a', 1.8);
    bodyHalo.position.set(0, 0, 0);
    scene.add(bodyHalo);
    return;
  }

  const rs = 2 * G * s.M / (C * C);
  let inner = RS_SCENE;
  if (s.R > rs) {
    const logx = Math.log10(s.R / rs);
    const t = Math.min(1, Math.max(0, logx / 10));
    inner = RS_SCENE + t * (R_MAX_SCENE * 0.92 - RS_SCENE);
  }

  flammGrid = new THREE.LineSegments(
    makeFlammWireGeometry(inner),
    new THREE.LineBasicMaterial({ color: 0xe7ecf5, transparent: true, opacity: 0.5 })
  );
  scene.add(flammGrid);

  // Body sphere (or black-hole disk) at the top of the well
  const style = BODY_STYLE[s.key] || BODY_STYLE.sun;
  const bodyZ = 2 * Math.sqrt(RS_SCENE * Math.max(0, inner - RS_SCENE));
  // visible body radius in scene units — at most 0.35 of inner so it sits in the well
  const bodyR = Math.min(0.55, inner * 0.42);

  bodyMesh = new THREE.Mesh(
    new THREE.SphereGeometry(bodyR, 48, 48),
    new THREE.MeshBasicMaterial({ color: style.core })
  );
  bodyMesh.position.set(0, -bodyZ + bodyR * 0.05, 0);
  scene.add(bodyMesh);

  // soft additive glow halo
  bodyHalo = makeGlowSprite(style.glow, bodyR * 6);
  bodyHalo.position.copy(bodyMesh.position);
  scene.add(bodyHalo);

  // horizon ring when R <= rs (BH state)
  if (s.R <= rs) {
    horizonRing = new THREE.Mesh(
      new THREE.TorusGeometry(RS_SCENE, 0.032, 16, 160),
      new THREE.MeshBasicMaterial({ color: 0xff5b8a })
    );
    horizonRing.rotation.x = Math.PI / 2;
    horizonRing.position.y = 0;
    scene.add(horizonRing);
  }
}

// ─────────── Resize / framing ───────────
function frameCamera() {
  let target = new THREE.Vector3(0, -1.5, 0);
  let radius = 6.5;
  if (wormhole) { target.set(0, 0, 0); radius = 7.2; }
  else if (flammGrid) {
    flammGrid.geometry.computeBoundingSphere();
    target.copy(flammGrid.geometry.boundingSphere.center);
    radius = flammGrid.geometry.boundingSphere.radius;
  }
  controls.target.copy(target);
  const vFov = camera.fov * Math.PI / 180;
  const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect);
  const r = radius * (wormhole ? 0.78 : 0.92);
  const dist = Math.max(r / Math.sin(vFov/2), r / Math.sin(hFov/2));
  const dir = camera.position.clone().sub(target);
  if (dir.lengthSq() < 1e-6) dir.set(0, 0.35, 1);
  dir.normalize();
  camera.position.copy(target).addScaledVector(dir, dist);
  camera.lookAt(target);
  camera.updateProjectionMatrix();
  controls.update();
}
function resize() {
  const w = Math.max(1, host.clientWidth), h = Math.max(1, host.clientHeight);
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  frameCamera();
}
new ResizeObserver(resize).observe(host);

// ─────────── Cinematic auto-camera ───────────
// Active during playback. Smoothly orbits around the target and breathes the
// camera distance in/out so static images become living shots.
const cinema = {
  active: false,
  t0: 0,
  baseDist: 14,
  baseTarget: new THREE.Vector3(0, -1.5, 0),
  amp: 0.22,         // dolly amplitude as fraction of baseDist
  speed: 0.14,       // orbit yaw speed (rad/s)
  pitchCenter: 0.55, // center pitch ≈ 31°
  pitchAmp: 0.50,    // ±28° → sweeps from near-top-down to almost flat-on
  pitchSpeed: 0.32,  // rad/s
};
function setCinema(on) {
  cinema.active = on;
  controls.enabled = !on;
  if (on) {
    cinema.t0 = performance.now() * 0.001;
    // capture current orbit radius around target
    cinema.baseDist = camera.position.distanceTo(controls.target);
    cinema.baseTarget.copy(controls.target);
  }
}

let t0 = performance.now();
let scene_t0 = performance.now();
function loop() {
  const t  = (performance.now() - t0) * 0.001;
  const ts = (performance.now() - scene_t0) * 0.001;

  // Geometry self-rotation (subtle, always on)
  if (wormhole)        wormhole.rotation.y  = t * 0.06;
  else if (flammGrid)  flammGrid.rotation.y = t * 0.04;
  if (horizonRing)     horizonRing.rotation.z = -t * 0.05;

  if (cinema.active) {
    const u = cinema.t0 ? (t - cinema.t0) : 0;
    // Smooth dolly: ease in close, drift out, dolly in
    const dollyPhase = 0.5 - 0.5 * Math.cos(u * 0.45);
    const dist = cinema.baseDist * (1 - cinema.amp * dollyPhase);
    // Yaw orbit
    const yaw = u * cinema.speed;
    // Big pitch sweep: clamp to keep above the well and avoid going under it
    const pitchRaw = cinema.pitchCenter + cinema.pitchAmp * Math.sin(u * cinema.pitchSpeed);
    const pitch = Math.max(0.12, Math.min(1.35, pitchRaw));
    const cx = cinema.baseTarget.x + dist * Math.cos(pitch) * Math.sin(yaw);
    const cy = cinema.baseTarget.y + dist * Math.sin(pitch);
    const cz = cinema.baseTarget.z + dist * Math.cos(pitch) * Math.cos(yaw);
    camera.position.set(cx, cy, cz);
    camera.lookAt(cinema.baseTarget);
  } else {
    controls.update();
  }
  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}
loop();

// ─────────── Physics ───────────
function physics(s) {
  const rs = 2 * G * s.M / (C * C);
  const Kat = (r) => 48 * G * G * s.M * s.M / ((C ** 4) * (r ** 6));
  const tidal = (r) => 2 * G * s.M / (r ** 3); // |Δa/Δr|
  return {
    rs,
    compactness: s.R > 0 ? rs / s.R : Infinity,
    K_surf: s.R > 0 ? Kat(Math.max(rs, s.R)) : Kat(rs),
    K_2rs: rs > 0 ? Kat(2 * rs) : 0,
    tidal_per_m: s.R > 0 ? tidal(s.R) : tidal(rs),
  };
}

// "Things everybody knows" energy yardsticks (joules)
const EVERYDAY = {
  TNT_KG:        4.184e6,            // 1 kg TNT
  HIROSHIMA:     6.3e13,             // ~15 kt
  TSAR_BOMBA:    2.1e17,             // 50 Mt H-bomb
  ALL_NUKES:     1.5e19,             // ≈3700 Mt global stockpile (SIPRI ~ 12k warheads)
  CHICXULUB:     4.2e23,             // dinosaur-killing asteroid impact
  SUN_LIFETIME:  1.2e44,             // Sun's total radiation over 10 Gyr
  WORLD_YEAR:    6.0e20,
  JUP_REST:      M_JUP * C * C,      // 1.7×10⁴⁴ J
};
function gateEnergy(b0) {
  const Ec = (C ** 4) * b0 / G;
  const Eq = HBAR * C / b0;
  return {
    Ec, Eq,
    M_eq: Ec / (C ** 2),
    M_eq_in_Msun: Ec / (M_SUN * C ** 2),
    in_Jupiter: Ec / EVERYDAY.JUP_REST,
    vs_world: Ec / EVERYDAY.WORLD_YEAR,
    vs_sun_rest: Ec / (M_SUN * C ** 2),
    vs_sun_life: Ec / EVERYDAY.SUN_LIFETIME,
    vs_chicxulub: Ec / EVERYDAY.CHICXULUB,
    vs_all_nukes: Ec / EVERYDAY.ALL_NUKES,
    vs_tsar: Ec / EVERYDAY.TSAR_BOMBA,
    vs_hiroshima: Ec / EVERYDAY.HIROSHIMA,
    ratio: Ec / Eq,
    antimatter_tonnes: Ec / (C * C) / 2 / 1000,
  };
}

// ─────────── DOM update ───────────
function setText(id, v) { const el = $(id); if (el) el.textContent = v; }

function renderScene(idx) {
  scene_i = idx;
  scene_t0 = performance.now();
  const s = SCENES[idx];
  document.querySelectorAll('.ssel').forEach((b) => b.classList.toggle('active', parseInt(b.dataset.i) === idx));
  $('storyTitle').textContent = s.title;
  $('storyBody').textContent  = s.body;
  $('sceneCaption').innerHTML = `<b>${s.name}.</b> ${s.title}`;
  buildScene(s);

  if (s.wormhole) {
    // freeze "Source" panel onto the wormhole math
    setText('sObj', 'Wormhole throat');
    setText('sM', '— (no source mass)');
    setText('sR', `b₀ = ${fmt(s.b0)} m`);
    setText('sRs', 'rs ↔ b₀ (geometric)');
    setText('sC', '—');
    setText('kSurf', '—');
    setText('k2Rs', '—');
    setText('tidal', '—');
  } else {
    const p = physics(s);
    setText('sObj', s.name);
    setText('sM', `${fmt(s.M)} kg (${fmt(s.M / M_SUN)} M☉)`);
    setText('sR', `${fmt(s.R)} m`);
    setText('sRs', `${fmt(p.rs)} m`);
    setText('sC', p.compactness >= 1 ? `${fmt(p.compactness)} (≥1 → inside r_s)` : fmt(p.compactness));
    setText('kSurf', `${fmt(p.K_surf)} m⁻⁴`);
    setText('k2Rs',  `${fmt(p.K_2rs)} m⁻⁴`);
    setText('tidal', `${fmt(p.tidal_per_m)} s⁻²`);
  }
  resize();
  // Re-seed cinema base after framing so each new scene starts from a fresh shot.
  if (cinema.active) setCinema(true);
  if (window.renderMathInElement) renderMathInElement(document.body, {
    delimiters: [{ left: '$$', right: '$$', display: true }, { left: '$', right: '$', display: false }],
  });
}

function updateGate() {
  const b0 = 10 ** parseFloat($('b0Input').value);
  $('b0Out').textContent = `  b₀ = ${fmt(b0)} m`;
  const g = gateEnergy(b0);
  setText('Ec',  `${fmt(g.Ec)} J  (${fmt(g.M_eq)} kg)`);
  setText('EcHiro',  `${fmt(g.vs_hiroshima)}  Hiroshima bombs`);
  setText('EcTsar',  `${fmt(g.vs_tsar)}  Tsar Bombas (50 Mt H-bomb)`);
  setText('EcNukes', `${fmt(g.vs_all_nukes)}  ×  ALL nukes on Earth, detonated at once`);
  setText('EcChicx', `${fmt(g.vs_chicxulub)}  ×  the asteroid that killed the dinosaurs`);
  setText('EcWorld', `${fmt(g.vs_world)}  years  of total world energy production`);
  setText('EcJup',   `${fmt(g.in_Jupiter)}  ×  Jupiter annihilated into pure energy`);
  setText('EcSunLife',`${fmt(g.vs_sun_life)}  ×  Sun's TOTAL output over 10 Gyr`);
  setText('EcSun',   `${fmt(g.vs_sun_rest)}  ×  Sun's rest-mass energy ($M_\\odot c^2$)`);
  setText('Eq',  `${fmt(g.Eq)} J`);
  setText('ratio', `${fmt(g.ratio)}  (≈ ${fmt(Math.log10(g.ratio))} orders of magnitude)`);
  setText('anti', `${fmt(g.antimatter_tonnes)} t  matter + antimatter`);
}

// ─────────── Wiring ───────────
document.querySelectorAll('.ssel').forEach((b) => b.addEventListener('click', () => renderScene(parseInt(b.dataset.i))));
$('b0Input').addEventListener('input', updateGate);
let playTimer = null;
$('playBtn').addEventListener('click', () => {
  if (playTimer) {
    clearInterval(playTimer); playTimer = null;
    setCinema(false);
    $('playBtn').textContent = '▶ Play';
    return;
  }
  $('playBtn').textContent = '⏸ Pause';
  setCinema(true);
  playTimer = setInterval(() => {
    renderScene((scene_i + 1) % SCENES.length);
  }, 4500);
});

// Expose cinema control so the demo recorder can force-enable it
window.__cinema = { on: () => setCinema(true), off: () => setCinema(false) };

renderScene(0);
updateGate();
resize();
