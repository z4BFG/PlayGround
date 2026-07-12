// Akina Downhill — three.js scene built from the parametric track spec.
// Builds: road ribbon (crown + inside gutters on hairpins), guardrails,
// cut/cliff embankments, forest, the lake at the start, and an AE86-style car
// that drives the course. Orbit with the mouse; press D to toggle drive/chase cam.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TRACK } from './track_data.js';

const V3 = THREE.Vector3;
const UP = new V3(0, 1, 0);

// ---------------------------------------------------------------- track frame
// Recenter to the model origin (average XZ) and lift so the base sits near y=0.
const pts = TRACK.centerline;
const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
const cz = pts.reduce((s, p) => s + p.z, 0) / pts.length;
const minY = Math.min(...pts.map(p => p.y));

const centers = pts.map(p => new V3(p.x - cx, p.y - minY, p.z - cz));

// Per-point tangent, right vector, and turn sign (for gutter placement).
const rights = [];
const tangents = [];
const turnSign = []; // +1 left turn, -1 right turn
for (let i = 0; i < centers.length; i++) {
  const a = centers[Math.max(0, i - 1)];
  const b = centers[Math.min(centers.length - 1, i + 1)];
  const t = new V3().subVectors(b, a).normalize();
  const r = new V3().crossVectors(t, UP).normalize(); // travel-right, horizontal
  tangents.push(t);
  rights.push(r);
  // curvature sign from change in heading around this point
  const t0 = new V3().subVectors(centers[i], centers[Math.max(0, i - 1)]);
  const t1 = new V3().subVectors(centers[Math.min(centers.length - 1, i + 1)], centers[i]);
  turnSign.push(Math.sign(new V3().crossVectors(t0, t1).y) || 1);
}

const HALF = TRACK.road.carriageway_width_m / 2;   // 3.0 m
const CROWN = TRACK.road.crown_m;                  // road center lift
const GUT_W = TRACK.road.gutter_width_m;           // gutter width
const GUT_D = TRACK.road.gutter_depth_m;           // gutter depth
const RAIL_OFF = TRACK.road.guardrail_offset_m;
const CUT_RUN = 26, CUT_RISE = 20;                 // uphill (cut) embankment
const CLIFF_RUN = 34, CLIFF_DROP = 40;             // downhill (cliff) side

// deterministic PRNG so trees/rocks are stable across reloads
let seed = 1337;
const rand = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };

// ------------------------------------------------------------------- renderer
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x1a2330);
scene.fog = new THREE.Fog(0x1a2330, 120, 900);

const camera = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, 0.5, 5000);
camera.position.set(60, 60, 120);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.copy(centers[0]);

// -------------------------------------------------------------------- lights
scene.add(new THREE.HemisphereLight(0x9ab0d0, 0x1f3020, 0.75));
const moon = new THREE.DirectionalLight(0xbcd0ff, 1.15);
moon.position.set(-300, 400, 200);
moon.castShadow = true;
moon.shadow.mapSize.set(2048, 2048);
const s = 700;
moon.shadow.camera.left = -s; moon.shadow.camera.right = s;
moon.shadow.camera.top = s; moon.shadow.camera.bottom = -s;
moon.shadow.camera.far = 2000;
scene.add(moon);
scene.add(new THREE.AmbientLight(0x33405c, 0.55));

// --------------------------------------------------------- build road + land
// For each cross-section we emit 5 profile points:
// [cutTop, leftEdge, crown, rightEdge, cliffBottom]  (left = -R = uphill side)
function profile(i) {
  const c = centers[i], r = rights[i];
  const off = (d, dy) => new V3(
    c.x + r.x * d, c.y + dy, c.z + r.z * d);
  return {
    cutTop:   off(-(HALF + CUT_RUN), CUT_RISE),
    leftEdge: off(-HALF, 0.0),
    crown:    off(0, CROWN),
    rightEdge:off(HALF, 0.0),
    cliffBot: off(HALF + CLIFF_RUN, -CLIFF_DROP),
  };
}

const roadPos = [], roadNorm = [];
const cutPos = [], cliffPos = [];
function quad(arr, a, b, c, d) { // two triangles a-b-c, a-c-d
  arr.push(a.x,a.y,a.z, b.x,b.y,b.z, c.x,c.y,c.z);
  arr.push(a.x,a.y,a.z, c.x,c.y,c.z, d.x,d.y,d.z);
}

for (let i = 0; i < centers.length - 1; i++) {
  const p = profile(i), q = profile(i + 1);
  // road surface: leftEdge -> crown -> rightEdge (two strips)
  quad(roadPos, p.leftEdge, q.leftEdge, q.crown, p.crown);
  quad(roadPos, p.crown, q.crown, q.rightEdge, p.rightEdge);
  // uphill cut embankment
  quad(cutPos, p.cutTop, q.cutTop, q.leftEdge, p.leftEdge);
  // downhill cliff
  quad(cliffPos, p.rightEdge, q.rightEdge, q.cliffBot, p.cliffBot);
}

function meshFrom(posArr, mat, shadow = true) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(posArr, 3));
  g.computeVertexNormals();
  const m = new THREE.Mesh(g, mat);
  m.receiveShadow = shadow;
  return m;
}

const roadMat = new THREE.MeshStandardMaterial({ color: 0x2b2d33, roughness: 0.95 });
const cutMat = new THREE.MeshStandardMaterial({ color: 0x2e3a24, roughness: 1 });
const cliffMat = new THREE.MeshStandardMaterial({ color: 0x27311d, roughness: 1 });
scene.add(meshFrom(roadPos, roadMat));
scene.add(meshFrom(cutPos, cutMat));
const cliff = meshFrom(cliffPos, cliffMat); cliff.castShadow = true; scene.add(cliff);

// center line (faded paint)
{
  const cl = centers.map(c => new V3(c.x, c.y + CROWN + 0.03, c.z));
  const g = new THREE.BufferGeometry().setFromPoints(cl);
  scene.add(new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0x6a6a55 })));
}

// ------------------------------------------------------------- inside gutters
// Recessed channel along the inside edge of the hairpins that carry a gutter.
{
  const gpos = [];
  for (let i = 0; i < centers.length - 1; i++) {
    if (!pts[i].gutter_inside) continue;
    const side = turnSign[i] >= 0 ? -1 : 1; // inside of the corner
    const mk = (k, d, dy) => {
      const c = centers[k], r = rights[k];
      return new V3(c.x + r.x * d, c.y + dy, c.z + r.z * d);
    };
    const eIn = side * (HALF - 0.05);
    const eOut = side * (HALF - 0.05 - GUT_W);
    const a = mk(i, eIn, -0.01), b = mk(i + 1, eIn, -0.01);
    const cc = mk(i + 1, eOut, -GUT_D), d = mk(i, eOut, -GUT_D);
    quad(gpos, a, b, cc, d);
  }
  if (gpos.length) {
    const gm = new THREE.MeshStandardMaterial({ color: 0x1a1c20, roughness: 1, side: THREE.DoubleSide });
    scene.add(meshFrom(gpos, gm));
  }
}

// ----------------------------------------------------------------- guardrails
// Continuous W-beam-ish ribbon on the cliff (right) edge + posts.
{
  const railH = 0.75, beamTop = 0.7, beamBot = 0.45;
  const top = [], bot = [];
  for (let i = 0; i < centers.length; i++) {
    const c = centers[i], r = rights[i];
    const d = HALF + RAIL_OFF;
    top.push(new V3(c.x + r.x * d, c.y + beamTop, c.z + r.z * d));
    bot.push(new V3(c.x + r.x * d, c.y + beamBot, c.z + r.z * d));
  }
  const rp = [];
  for (let i = 0; i < centers.length - 1; i++)
    quad(rp, top[i], top[i + 1], bot[i + 1], bot[i]);
  const railMat = new THREE.MeshStandardMaterial({
    color: 0x9aa4ad, metalness: 0.85, roughness: 0.35, side: THREE.DoubleSide });
  const rail = meshFrom(rp, railMat, false); rail.castShadow = true; scene.add(rail);

  // posts every ~8 m
  const postGeo = new THREE.CylinderGeometry(0.06, 0.06, railH, 6);
  const postMat = new THREE.MeshStandardMaterial({ color: 0x6b7278, metalness: 0.7, roughness: 0.5 });
  const step = 8, count = Math.floor((centers.length * 6) / step);
  const posts = new THREE.InstancedMesh(postGeo, postMat, count);
  const dummy = new THREE.Object3D();
  let n = 0;
  for (let i = 0; i < centers.length && n < count; i += Math.round(step / 6)) {
    const c = centers[i], r = rights[i], d = HALF + RAIL_OFF;
    dummy.position.set(c.x + r.x * d, c.y + railH / 2, c.z + r.z * d);
    dummy.updateMatrix(); posts.setMatrixAt(n++, dummy.matrix);
  }
  posts.count = n; posts.castShadow = true; scene.add(posts);
}

// ---------------------------------------------------------------------- trees
// Instanced conifers scattered on both embankments, denser away from the road.
{
  const trunkGeo = new THREE.CylinderGeometry(0.18, 0.28, 2.2, 5);
  const coneGeo = new THREE.ConeGeometry(1.6, 6, 7);
  const positions = [];
  for (let i = 2; i < centers.length - 2; i += 1) {
    for (const side of [-1, 1]) {
      if (rand() > 0.85) continue;
      const c = centers[i], r = rights[i];
      const base = HALF + 4 + rand() * (side < 0 ? CUT_RUN : CLIFF_RUN);
      const d = side * base;
      const dyBase = side < 0 ? (base / CUT_RUN) * CUT_RISE : -(base / CLIFF_RUN) * CLIFF_DROP;
      const jx = (rand() - 0.5) * 3, jz = (rand() - 0.5) * 3;
      positions.push({
        x: c.x + r.x * d + jx, y: c.y + dyBase, z: c.z + r.z * d + jz,
        sc: 0.7 + rand() * 1.1,
      });
    }
  }
  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x3a2a1c, roughness: 1 });
  const coneMat = new THREE.MeshStandardMaterial({ color: 0x1f3a22, roughness: 1 });
  const trunks = new THREE.InstancedMesh(trunkGeo, trunkMat, positions.length);
  const cones = new THREE.InstancedMesh(coneGeo, coneMat, positions.length);
  const dummy = new THREE.Object3D();
  positions.forEach((p, k) => {
    dummy.position.set(p.x, p.y + 1.1 * p.sc, p.z); dummy.scale.setScalar(p.sc);
    dummy.updateMatrix(); trunks.setMatrixAt(k, dummy.matrix);
    dummy.position.set(p.x, p.y + (2.2 + 3) * p.sc, p.z);
    dummy.updateMatrix(); cones.setMatrixAt(k, dummy.matrix);
  });
  cones.castShadow = true;
  scene.add(trunks); scene.add(cones);
}

// ----------------------------------------------------------------------- lake
// Lake Akina near the start (sector S0).
{
  const start = centers[0];
  const lake = new THREE.Mesh(
    new THREE.CircleGeometry(90, 48),
    new THREE.MeshStandardMaterial({ color: 0x16304a, roughness: 0.15, metalness: 0.4 }));
  lake.rotation.x = -Math.PI / 2;
  lake.position.set(start.x - rights[0].x * 130, start.y - 3, start.z - rights[0].z * 130);
  scene.add(lake);
}

// ------------------------------------------------------------------------ car
// Simple AE86-style hatch: white body, black lower + hood, four wheels.
function buildCar() {
  const g = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(1.6, 0.5, 3.9),
    new THREE.MeshStandardMaterial({ color: 0xf2f2f2, roughness: 0.5, metalness: 0.2 }));
  body.position.y = 0.55; body.castShadow = true; g.add(body);
  const cabin = new THREE.Mesh(
    new THREE.BoxGeometry(1.45, 0.45, 1.9),
    new THREE.MeshStandardMaterial({ color: 0xf2f2f2, roughness: 0.5 }));
  cabin.position.set(0, 0.98, -0.1); cabin.castShadow = true; g.add(cabin);
  const lower = new THREE.Mesh(
    new THREE.BoxGeometry(1.62, 0.28, 3.95),
    new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.7 }));
  lower.position.y = 0.33; g.add(lower);
  const hood = new THREE.Mesh(
    new THREE.BoxGeometry(1.5, 0.06, 1.5),
    new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.6 }));
  hood.position.set(0, 0.82, 1.05); g.add(hood);
  const wheelGeo = new THREE.CylinderGeometry(0.34, 0.34, 0.28, 14);
  const wheelMat = new THREE.MeshStandardMaterial({ color: 0x0a0a0a, roughness: 0.8 });
  for (const [wx, wz] of [[0.8, 1.3], [-0.8, 1.3], [0.8, -1.3], [-0.8, -1.3]]) {
    const w = new THREE.Mesh(wheelGeo, wheelMat);
    w.rotation.z = Math.PI / 2; w.position.set(wx, 0.34, wz); g.add(w);
  }
  // headlights
  const hl = new THREE.SpotLight(0xfff4d6, 6, 90, 0.5, 0.4, 1.2);
  hl.position.set(0, 0.6, 1.9); hl.target.position.set(0, 0, 30);
  g.add(hl); g.add(hl.target);
  return g;
}
const car = buildCar();
scene.add(car);

// ----------------------------------------------------------------- drive loop
let driving = true, t = 0;               // t = fractional index along centerline
// ?t=INDEX jumps to a point and pauses the drive (inspection / screenshots)
const qT = new URLSearchParams(location.search).get('t');
if (qT !== null) {
  t = Math.max(0, Math.min(centers.length - 2, +qT || 0)); driving = false;
  const i = Math.floor(t);
  const back = tangents[i].clone().multiplyScalar(-14);
  camera.position.copy(centers[i]).add(back).add(new V3(6, 8, 0));
  controls.target.copy(centers[i]);
}
const tmpPos = new V3(), tmpLook = new V3();
addEventListener('keydown', e => { if (e.key.toLowerCase() === 'd') driving = !driving; });

function placeCar() {
  const i = Math.floor(t) % (centers.length - 1);
  const f = t - Math.floor(t);
  tmpPos.copy(centers[i]).lerp(centers[i + 1], f);
  const ahead = (i + 6) % centers.length;
  tmpLook.copy(centers[ahead]);
  car.position.copy(tmpPos); car.position.y += 0.05;
  car.lookAt(tmpLook.x, car.position.y, tmpLook.z);
  if (driving) {
    // chase cam
    const back = tangents[i].clone().multiplyScalar(-11);
    const camPos = tmpPos.clone().add(back); camPos.y += 5.5;
    camera.position.lerp(camPos, 0.06);
    controls.target.lerp(tmpLook, 0.1);
  }
}

// ---------------------------------------------------------------------- HUD
const hud = document.getElementById('hud');
function updateHud() {
  const i = Math.floor(t) % centers.length;
  const p = pts[i];
  hud.querySelector('#sector').textContent = `${p.sector} · ${sectorName(p.sector)}`;
  hud.querySelector('#stat').textContent =
    `elev ${(p.y).toFixed(0)} m · grade ${p.grade_pct}%` +
    (p.hairpin ? ' · HAIRPIN' : '') + (p.gutter_inside ? ' · gutter' : '');
}
function sectorName(id) {
  return (TRACK.sectors.find(s => s.id === id) || {}).name || id;
}

// -------------------------------------------------------------------- animate
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

function animate() {
  requestAnimationFrame(animate);
  if (driving) { t += 0.35; if (t >= centers.length - 1) t = 0; }
  placeCar();
  updateHud();
  controls.update();
  renderer.render(scene, camera);
}
animate();

// ------------------------------------------------------- debug / capture hook
// Lets tooling (e.g. headless screenshots) park the car and frame any angle.
window.__akina = {
  THREE, scene, camera, controls, car, centers, tangents, rights,
  setT(v) { t = Math.max(0, Math.min(centers.length - 2, v)); driving = false; placeCar(); },
  drive(b) { driving = !!b; },
  look(camPos, target) {
    driving = false;
    camera.position.set(camPos[0], camPos[1], camPos[2]);
    controls.target.set(target[0], target[1], target[2]);
    controls.update();
  },
  bbox() {
    const b = new THREE.Box3().setFromPoints(centers);
    return { min: b.min.toArray(), max: b.max.toArray(),
             center: b.getCenter(new V3()).toArray(), size: b.getSize(new V3()).toArray() };
  },
};
