// Generates lounge.glb — the fixed cosy lounge environment for
// private-quest-lounge. All geometry is procedural and original (no external
// assets). Hubs behaviour (nav mesh, spawn points, seat waypoints, lights) is
// injected as MOZ_hubs_components node extensions after export.
//
// Usage: node generate-lounge.mjs [outfile]

// Minimal FileReader shim: GLTFExporter assumes a browser.
globalThis.FileReader ??= class {
  readAsArrayBuffer(blob) {
    blob.arrayBuffer().then(r => {
      this.result = r;
      this.onloadend?.();
    });
  }
  readAsDataURL(blob) {
    blob.arrayBuffer().then(r => {
      this.result = `data:${blob.type};base64,${Buffer.from(r).toString("base64")}`;
      this.onloadend?.();
    });
  }
};

import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { writeFileSync } from "fs";

const out = process.argv[2] || "lounge.glb";

// ---------------------------------------------------------------------------
// Materials — flat colours only; warmth comes from lighting.
// ---------------------------------------------------------------------------
const M = {
  floor: mat(0x40342a, { roughness: 0.55 }), // dark walnut plank
  logWall: new THREE.MeshStandardMaterial({ name: "LogWall", color: 0xf1ede4, roughness: 0.95, metalness: 0 }), // warm white plaster (name kept for embed plumbing)
  wall: mat(0xf1ede4, { roughness: 0.95 }),
  ceiling: mat(0xf6f4ef, { roughness: 0.95 }),
  trim: mat(0x23252a, { roughness: 0.45, metalness: 0.4 }), // blackened-steel window frames
  couchA: mat(0xe6dfd0, { roughness: 0.9 }), // cream boucle
  couchB: mat(0x393d44, { roughness: 0.9 }), // charcoal
  cushionA: mat(0xd8d0bd, { roughness: 0.95 }),
  cushionB: mat(0x4b5058, { roughness: 0.95 }),
  throw1: mat(0xb98a4e, { roughness: 0.95 }), // camel
  throw2: mat(0xefe9dc, { roughness: 0.95 }), // ivory
  wood: mat(0x2c2118, { roughness: 0.5 }),    // black-walnut furniture
  rug: mat(0xaaa79e, { roughness: 1.0 }),     // pale grey wool
  rugInner: mat(0xc6c2b8, { roughness: 1.0 }),
  lampShade: new THREE.MeshStandardMaterial({
    color: 0xfff1d8,
    emissive: 0xffe3b0,
    emissiveIntensity: 1.6,
    roughness: 0.9
  }),
  lampMetal: mat(0x8f7a3f, { roughness: 0.35, metalness: 0.85 }), // brushed brass
  nightGlass: new THREE.MeshStandardMaterial({
    color: 0x0a1226,
    emissive: 0x101d3a,
    emissiveIntensity: 1.0,
    roughness: 0.4
  }),
  moon: new THREE.MeshStandardMaterial({
    color: 0xf5eeda,
    emissive: 0xf5eeda,
    emissiveIntensity: 2.0
  }),
  frame: mat(0x1c1c1f, { roughness: 0.5 }),
  art1a: mat(0x1f3a5f, { roughness: 0.9 }), // deep navy abstract
  art1b: mat(0xc8a24b, { roughness: 0.6, metalness: 0.3 }), // gold-leaf accent
  art2a: mat(0xd8c8bb, { roughness: 0.9 }), // blush/greige abstract
  art2b: mat(0x6a6f76, { roughness: 0.9 }),
  book: mat(0x22262e, { roughness: 0.9 }),
  mug: mat(0xf2efe8, { roughness: 0.7 }),
  plantPot: mat(0x2e3033, { roughness: 0.8 }),
  plant: mat(0x3f6b3a, { roughness: 0.95 }),
  // Kitchen
  cabinet: mat(0x2b2d30, { roughness: 0.6 }),          // matte graphite fronts
  marble: mat(0xe9e6df, { roughness: 0.25 }),           // honed white stone
  steel: mat(0x9ba0a6, { roughness: 0.35, metalness: 0.8 }), // appliance fronts
  brass: mat(0x8f7a3f, { roughness: 0.35, metalness: 0.85 })
};
function mat(color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, metalness: 0, ...opts });
}

const scene = new THREE.Scene();
scene.name = "CosyLounge";

function box(name, w, h, d, material, x, y, z, ry = 0) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
  m.name = name;
  m.position.set(x, y, z);
  m.rotation.y = ry;
  scene.add(m);
  return m;
}
function cyl(name, rTop, rBot, h, material, x, y, z, seg = 12) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(rTop, rBot, h, seg), material);
  m.name = name;
  m.position.set(x, y, z);
  scene.add(m);
  return m;
}
// Box with UVs scaled so a square tiling texture repeats every `period` metres.
function texturedBox(name, w, h, d, material, x, y, z, period) {
  const geo = new THREE.BoxGeometry(w, h, d);
  const uv = geo.attributes.uv;
  const ru = Math.max(w, d) / period, rv = h / period;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * ru, uv.getY(i) * rv);
  const m = new THREE.Mesh(geo, material);
  m.name = name;
  m.position.set(x, y, z);
  scene.add(m);
  return m;
}

// ---------------------------------------------------------------------------
// Room shell: 12 wide (x, extended to the west) x 10 deep (z) x 3 high.
// Manhattan penthouse: the whole north wall is floor-to-ceiling glass looking
// out over Central Park (view images cycle via lounge/view-switcher.js).
// ---------------------------------------------------------------------------
const X_MIN = -9, X_MAX = 3, Z_MIN = -5, Z_MAX = 5;
const W = X_MAX - X_MIN, D = Z_MAX - Z_MIN, T = 0.12; // wall thickness
const H = 3;        // south-wall height
const H_N = 4.5;    // glass-wall height (5 ft higher); roof slopes up to it
const CX = (X_MIN + X_MAX) / 2, CZ = (Z_MIN + Z_MAX) / 2;
const LOG_PERIOD = 1.8; // metres of wall per texture tile (~6 logs)
box("Floor", W, T, D, M.floor, CX, -T / 2, CZ);
// Sloped ceiling rising from the south wall (3 m) to the glass wall (4.5 m)
const slope = Math.atan((H_N - H) / D);
const roof = box("Roof", W, T, D / Math.cos(slope) + 0.2, M.ceiling, CX, (H + H_N) / 2 + T / 2, CZ);
roof.rotation.x = slope;
// Log walls (east/west run full height; the roof hides their tops)
texturedBox("Wall_East", T, H_N, D, M.logWall, X_MAX + T / 2, H_N / 2, CZ, LOG_PERIOD);
texturedBox("Wall_West", T, H_N, D, M.logWall, X_MIN - T / 2, H_N / 2, CZ, LOG_PERIOD);
texturedBox("Wall_South", W + 2 * T, H, T, M.logWall, CX, H / 2, Z_MAX + T / 2, LOG_PERIOD);

// North glass wall: slim rails top/bottom, mullion posts, one big pane.
const nz = Z_MIN;
box("GlassRail_B", W, 0.09, 0.14, M.trim, CX, 0.045, nz);
box("GlassRail_T", W, 0.09, 0.14, M.trim, CX, H_N - 0.045, nz);
for (let i = 0; i <= 5; i++) {
  const mx = X_MIN + (W / 5) * i;
  box(`GlassMullion_${i}`, 0.07, H_N, 0.12, M.trim, Math.min(Math.max(mx, X_MIN + 0.035), X_MAX - 0.035), H_N / 2, nz);
}
const glassMat = new THREE.MeshStandardMaterial({
  color: 0xbcd6e0,
  transparent: true,
  opacity: 0.1,
  roughness: 0.05,
  metalness: 0
});
box("GlassWall", W, H_N, 0.02, glassMat, CX, H_N / 2, nz);

// Rockies backdrop outside the glass (textured in post-processing).
const backdropMat = new THREE.MeshStandardMaterial({
  name: "RockiesBackdrop",
  color: 0x000000,
  emissive: 0xffffff,
  emissiveIntensity: 1.0,
  roughness: 1,
  metalness: 0
});
const backdropGeo = new THREE.PlaneGeometry(26, 13);
// glTF UV convention: v=0 is the image top; flip three.js default.
{
  const uv = backdropGeo.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setY(i, 1 - uv.getY(i));
}
const backdrop = new THREE.Mesh(backdropGeo, backdropMat);
backdrop.name = "RockiesView";
backdrop.position.set(CX, 4.0, nz - 1.8);
scene.add(backdrop);

// Skirting (no skirt on the glass wall)
box("Skirt_S", W, 0.1, 0.03, M.trim, CX, 0.05, Z_MAX - 0.015);
box("Skirt_E", 0.03, 0.1, D, M.trim, X_MAX - 0.015, 0.05, CZ);
box("Skirt_W", 0.03, 0.1, D, M.trim, X_MIN + 0.015, 0.05, CZ);

// ---------------------------------------------------------------------------
// Rug + coffee table + decor
// ---------------------------------------------------------------------------
box("Rug", 2.4, 0.02, 3.4, M.rug, 0, 0.011, 0);
box("RugInner", 2.0, 0.021, 3.0, M.rugInner, 0, 0.012, 0);

const tbl = { w: 1.1, d: 0.6, h: 0.42 };
box("Table_Top", tbl.w, 0.05, tbl.d, M.wood, 0, tbl.h, 0);
for (const [i, [lx, lz]] of [[-1, -1], [1, -1], [-1, 1], [1, 1]].entries()) {
  box(`Table_Leg${i}`, 0.05, tbl.h, 0.05, M.wood, lx * (tbl.w / 2 - 0.06), tbl.h / 2, lz * (tbl.d / 2 - 0.06));
}
box("Book", 0.22, 0.03, 0.15, M.book, -0.25, tbl.h + 0.04, 0.05, 0.4);
cyl("Mug1", 0.04, 0.035, 0.09, M.mug, 0.28, tbl.h + 0.07, 0.1);
cyl("Mug2", 0.04, 0.035, 0.09, M.mug, 0.18, tbl.h + 0.07, -0.14);

// ---------------------------------------------------------------------------
// Two couches facing each other across the table (couch A faces -z, B faces +z)
// ---------------------------------------------------------------------------
function couch(tag, z, facing, bodyMat, cushMat, throwMat, x = 0, rotY = 0) {
  // facing = -1 → looks toward -z (couch sits at +z)
  const g = new THREE.Group();
  g.name = `Couch_${tag}`;
  const cw = 1.9, cd = 0.85, seatH = 0.42;
  const parts = [];
  const add = (name, w, h, d, m, x, y, zz) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
    mesh.name = name;
    mesh.position.set(x, y, zz);
    g.add(mesh);
    parts.push(mesh);
  };
  add(`${tag}_Base`, cw, 0.3, cd, bodyMat, 0, 0.15, 0);
  add(`${tag}_Back`, cw, 0.55, 0.2, bodyMat, 0, 0.55, facing * -1 * (cd / 2 - 0.1));
  add(`${tag}_ArmL`, 0.18, 0.35, cd, bodyMat, -cw / 2 + 0.09, 0.47, 0);
  add(`${tag}_ArmR`, 0.18, 0.35, cd, bodyMat, cw / 2 - 0.09, 0.47, 0);
  // seat cushions
  add(`${tag}_CushL`, 0.8, 0.14, cd - 0.28, cushMat, -0.44, 0.37, facing * 0.06);
  add(`${tag}_CushR`, 0.8, 0.14, cd - 0.28, cushMat, 0.44, 0.37, facing * 0.06);
  // back cushions
  add(`${tag}_BackCushL`, 0.78, 0.4, 0.12, cushMat, -0.44, 0.62, facing * -1 * (cd / 2 - 0.24));
  add(`${tag}_BackCushR`, 0.78, 0.4, 0.12, cushMat, 0.44, 0.62, facing * -1 * (cd / 2 - 0.24));
  // throw pillow
  const pil = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.3, 0.12), throwMat);
  pil.name = `${tag}_Pillow`;
  pil.position.set(-cw / 2 + 0.32, 0.6, facing * -1 * (cd / 2 - 0.3));
  pil.rotation.z = 0.5;
  g.add(pil);
  g.position.set(x, 0, z);
  g.rotation.y = rotY;
  scene.add(g);
  return { seatH, cushionX: [-0.44, 0.44], z };
}
const couchA = couch("A", 1.55, -1, M.couchA, M.cushionA, M.throw1); // faces the window
const couchB = couch("B", -1.55, 1, M.couchB, M.cushionB, M.throw2);
// TV couch: west end, rotated to face the wall TV (-x). Local -z maps to -x.
couch("C", 0, -1, M.couchA, M.cushionA, M.throw2, -4.6, Math.PI / 2);
// World-space cushion centers for couch C (local ±0.44 x, -0.06 z, rotated 90°)
const couchC = { cushions: [[-4.66, 0.44], [-4.66, -0.44]] };

// ---------------------------------------------------------------------------
// Floor lamps (emissive shades; real lights injected as hubs point-lights)
// ---------------------------------------------------------------------------
function lamp(tag, x, z) {
  cyl(`Lamp${tag}_Base`, 0.16, 0.18, 0.04, M.lampMetal, x, 0.02, z);
  cyl(`Lamp${tag}_Pole`, 0.02, 0.02, 1.45, M.lampMetal, x, 0.76, z);
  cyl(`Lamp${tag}_Shade`, 0.14, 0.2, 0.3, M.lampShade, x, 1.55, z, 16);
  // Light anchor node (no geometry)
  const anchor = new THREE.Object3D();
  anchor.name = `Lamp${tag}_Light`;
  anchor.position.set(x, 1.45, z);
  scene.add(anchor);
}
lamp("C", -6.6, -3.9);
lamp("D", -6.6, 3.9);

// ---------------------------------------------------------------------------
// Wall art (east + west walls)
// ---------------------------------------------------------------------------
function art(tag, x, z, ry, a, b) {
  const g = new THREE.Group();
  g.name = `Art_${tag}`;
  const f = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.7, 0.03), M.frame);
  f.name = `Art_${tag}_Frame`;
  g.add(f);
  const c1 = new THREE.Mesh(new THREE.BoxGeometry(0.78, 0.58, 0.032), a);
  c1.name = `Art_${tag}_Canvas`;
  c1.position.z = 0.002;
  g.add(c1);
  const c2 = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.34, 0.036), b);
  c2.name = `Art_${tag}_Accent`;
  c2.position.set(0.14, -0.06, 0.004);
  c2.rotation.z = 0.2;
  g.add(c2);
  g.position.set(x, 1.7, z);
  g.rotation.y = ry;
  scene.add(g);
}
art("East", X_MAX - 0.03, -1.0, -Math.PI / 2, M.art1a, M.art1b); // north of the fridge
art("West", X_MIN + 0.03, -3.0, Math.PI / 2, M.art2a, M.art2b); // shifted for the TV

// ---------------------------------------------------------------------------
// Wall TV (west wall, faces the dining table and the couches beyond).
// The dark "TVScreen" plane is the pin target: lounge/tv.js snaps any
// screen-share video object onto it.
// ---------------------------------------------------------------------------
const TV = { w: 3.2, h: 1.8, cy: 1.6, cz: 0 };
box("TV_Frame", 0.08, TV.h + 0.12, TV.w + 0.12, mat(0x1a1a1a, { roughness: 0.4 }), X_MIN + 0.06, TV.cy, TV.cz);
{
  const scr = new THREE.Mesh(
    new THREE.PlaneGeometry(TV.w, TV.h),
    new THREE.MeshStandardMaterial({ color: 0x05070a, roughness: 0.3, metalness: 0.1 })
  );
  scr.name = "TVScreen";
  scr.position.set(X_MIN + 0.11, TV.cy, TV.cz);
  scr.rotation.y = Math.PI / 2; // face +x, into the room
  scene.add(scr);
}

// Plant in the corner
cyl("Plant_Pot", 0.16, 0.12, 0.28, M.plantPot, 2.5, 0.14, -2.0);
cyl("Plant_Leaves", 0.02, 0.28, 0.75, M.plant, 2.5, 0.75, -2.0, 8);

// ---------------------------------------------------------------------------
// Kitchen (east wall): graphite cabinet run + marble tops, fridge at the north
// end, marble island with three brass stools facing the kitchen. Stools are
// seat waypoints (Seat_S1..S3) with floor-level nav islands like the chairs.
// ---------------------------------------------------------------------------
const KIT = { cx: 2.65, z1: 1.35, z2: 4.6 };
{
  const len = KIT.z2 - KIT.z1, zc = (KIT.z1 + KIT.z2) / 2;
  box("Kitchen_Base", 0.7, 0.86, len, M.cabinet, KIT.cx, 0.43, zc);
  box("Kitchen_Top", 0.76, 0.04, len + 0.06, M.marble, KIT.cx, 0.9, zc);
  box("Kitchen_Splash", 0.02, 0.6, len, M.marble, X_MAX - 0.02, 1.22, zc);
  box("Kitchen_Uppers", 0.35, 0.7, len - 0.4, M.cabinet, X_MAX - 0.185, 2.0, zc);
  // Cooktop + brass faucet
  box("Kitchen_Cooktop", 0.55, 0.015, 0.5, mat(0x0c0d10, { roughness: 0.3 }), KIT.cx - 0.02, 0.925, 3.6);
  cyl("Kitchen_Faucet", 0.018, 0.018, 0.3, M.brass, X_MAX - 0.18, 1.05, 2.2, 10);
  // Fridge (north end of the run, integrated panel look)
  box("Kitchen_Fridge", 0.78, 2.05, 0.75, M.steel, 2.6, 1.025, 0.9);
  box("Kitchen_FridgeHandle", 0.02, 0.9, 0.03, M.brass, 2.2, 1.2, 0.58);
}
// Island — kept south of couch A (couch A footprint reaches z ≈ 1.97)
const ISL = { x: 1.3, z: 3.4, w: 0.95, len: 2.0 };
box("Island_Base", ISL.w - 0.12, 0.86, ISL.len - 0.12, M.cabinet, ISL.x, 0.43, ISL.z);
box("Island_Top", ISL.w, 0.04, ISL.len + 0.1, M.marble, ISL.x, 0.9, ISL.z);
// Stools (west side, facing the kitchen: +x)
const STOOLS = [
  ["S1", 0.55, 2.7],
  ["S2", 0.55, 3.4],
  ["S3", 0.55, 4.1]
];
for (const [tag, sx, sz] of STOOLS) {
  cyl(`Stool_${tag}_Base`, 0.14, 0.16, 0.03, M.brass, sx, 0.015, sz);
  cyl(`Stool_${tag}_Pole`, 0.022, 0.022, 0.56, M.brass, sx, 0.31, sz, 10);
  cyl(`Stool_${tag}_Seat`, 0.17, 0.17, 0.05, M.wood, sx, 0.62, sz, 16);
}
// Pendant globes over the island (emissive only — no extra dynamic lights).
// Stems run from the globe up to the sloped ceiling at that z.
for (const [i, pz] of [[0, 2.8], [1, 3.4], [2, 4.0]]) {
  const ceilY = H + (H_N - H) * (Z_MAX - pz) / D;
  const stemH = ceilY - 2.29;
  cyl(`Pendant${i}_Stem`, 0.008, 0.008, stemH, M.brass, ISL.x, 2.29 + stemH / 2, pz, 8);
  const globe = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 12), M.lampShade);
  globe.name = `Pendant${i}_Globe`;
  globe.position.set(ISL.x, 2.2, pz);
  scene.add(globe);
}

// ---------------------------------------------------------------------------
// TV couch (west end): faces the wall TV across the room. Same seat mechanism
// as the other couches. Built at origin facing local -z, rotated to face -x.
// ---------------------------------------------------------------------------
const SEAT_H = 0.45;
function chair(tag, cx, cz, yaw) {
  const g = new THREE.Group();
  g.name = `Chair_${tag}`;
  const add = (name, w, h, d, m, x, y, z) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
    mesh.name = `Chair_${tag}_${name}`;
    mesh.position.set(x, y, z);
    g.add(mesh);
  };
  add("Seat", 0.46, 0.06, 0.44, M.cushionB, 0, SEAT_H - 0.03, 0);
  for (const [i, [lx, lz]] of [[-1, -1], [1, -1], [-1, 1], [1, 1]].entries()) {
    add(`Leg${i}`, 0.045, SEAT_H - 0.06, 0.045, M.wood, lx * 0.19, (SEAT_H - 0.06) / 2, lz * 0.18);
  }
  add("Back", 0.46, 0.5, 0.05, M.wood, 0, SEAT_H + 0.28, -0.21);
  // group +z is the sitting direction; back sits behind (-z), then yaw
  g.position.set(cx, 0, cz);
  g.rotation.y = yaw;
  scene.add(g);
}

// ---------------------------------------------------------------------------
// Work desk (south-west corner): desk against the south wall, two chairs side
// by side, monitor on top. The monitor mirrors the wall-TV share up close so
// seated text is legible (lounge/tv.js shares the video material).
// ---------------------------------------------------------------------------
const DESK = { x: -7.5, z: 4.45, w: 1.6, d: 0.7, h: 0.74 };
box("Desk_Top", DESK.w, 0.05, DESK.d, M.wood, DESK.x, DESK.h, DESK.z);
for (const [i, [lx, lz]] of [[-1, -1], [1, -1], [-1, 1], [1, 1]].entries()) {
  box(`Desk_Leg${i}`, 0.06, DESK.h, 0.06, M.wood,
    DESK.x + lx * (DESK.w / 2 - 0.08), DESK.h / 2, DESK.z + lz * (DESK.d / 2 - 0.1));
}
// Monitor: 16:9 panel on a stand, facing the chairs (-z)
box("Monitor_Stand", 0.06, 0.12, 0.18, M.lampMetal, DESK.x, DESK.h + 0.085, DESK.z + 0.12);
box("Monitor_Frame", 1.12, 0.66, 0.03, mat(0x1a1a1a, { roughness: 0.4 }), DESK.x, DESK.h + 0.52, DESK.z + 0.14);
{
  const mon = new THREE.Mesh(
    new THREE.PlaneGeometry(1.06, 0.6),
    new THREE.MeshStandardMaterial({ color: 0x05070a, roughness: 0.3, metalness: 0.1 })
  );
  mon.name = "MonitorScreen";
  mon.position.set(DESK.x, DESK.h + 0.52, DESK.z + 0.122);
  mon.rotation.y = Math.PI; // face -z, toward the chairs
  scene.add(mon);
}
const DESK_CHAIRS = [
  ["K1", DESK.x - 0.4, DESK.z - 0.73, 0],
  ["K2", DESK.x + 0.4, DESK.z - 0.73, 0]
];
for (const [tag, cx, cz, yaw] of DESK_CHAIRS) chair(tag, cx, cz, yaw);

// ---------------------------------------------------------------------------
// Nav mesh: one welded triangulated grid over the whole floor, cells dropped
// inside furniture footprints. Abutting separate rectangles do NOT count as
// connected in three-pathfinding (neighbors need a shared edge, i.e. two
// shared vertices), which stranded players on isolated patches. A grid built
// from a single shared vertex lattice is connected by construction.
// ---------------------------------------------------------------------------
const NAV = { x1: -8.85, z1: -4.85, x2: 2.85, z2: 4.85, res: 0.2 };
// Blocked footprints [x1, z1, x2, z2] (slightly expanded past the geometry)
const blocked = [
  [-1.15, 1.05, 1.15, 2.05],   // couch A
  [-1.15, -2.05, 1.15, -1.05], // couch B
  [-0.7, -0.45, 0.7, 0.45],    // coffee table
  [-6.8, -4.1, -6.4, -3.7],    // lamp C
  [-6.8, 3.7, -6.4, 4.1],      // lamp D
  [2.28, -2.22, 2.72, -1.78],  // plant
  [-5.2, -1.1, -4.05, 1.1],    // TV couch (couch C)
  [-8.4, 4.0, -6.6, 4.85],     // desk
  [-8.18, 3.48, -7.62, 3.98],  // desk chair K1
  [-7.38, 3.48, -6.82, 3.98],  // desk chair K2
  [2.2, 0.4, 2.9, 4.85],       // kitchen run + fridge (east wall)
  [0.75, 2.3, 1.85, 4.5],      // island
  [0.35, 2.5, 0.75, 2.9],      // stool S1
  [0.35, 3.2, 0.75, 3.6],      // stool S2
  [0.35, 3.9, 0.75, 4.3]       // stool S3
];
const inBlocked = (x, z) => blocked.some(([a, b, c, d]) => x > a && x < c && z > b && z < d);
const navGeoms = [];
{
  const nx = Math.round((NAV.x2 - NAV.x1) / NAV.res);
  const nz = Math.round((NAV.z2 - NAV.z1) / NAV.res);
  const dx = (NAV.x2 - NAV.x1) / nx;
  const dz = (NAV.z2 - NAV.z1) / nz;
  const vIndex = new Map(); // lattice (i,j) -> vertex index, shared across cells
  const pos = [];
  const idx = [];
  const vert = (i, j) => {
    const k = i * (nz + 1) + j;
    let v = vIndex.get(k);
    if (v === undefined) {
      v = pos.length / 3;
      vIndex.set(k, v);
      pos.push(NAV.x1 + i * dx, 0.002, NAV.z1 + j * dz);
    }
    return v;
  };
  for (let i = 0; i < nx; i++) {
    for (let j = 0; j < nz; j++) {
      const cx = NAV.x1 + (i + 0.5) * dx;
      const cz = NAV.z1 + (j + 0.5) * dz;
      if (inBlocked(cx, cz)) continue;
      const a = vert(i, j), b = vert(i + 1, j), c = vert(i + 1, j + 1), d = vert(i, j + 1);
      idx.push(a, c, b, a, d, c); // ccw viewed from above (+y)
    }
  }
  const gm = new THREE.BufferGeometry();
  gm.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  const uvs = [];
  for (let v = 0; v < pos.length; v += 3) {
    uvs.push((pos[v] - NAV.x1) / (NAV.x2 - NAV.x1), (pos[v + 2] - NAV.z1) / (NAV.z2 - NAV.z1));
  }
  gm.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  gm.setIndex(idx);
  gm.computeVertexNormals();
  navGeoms.push(gm);
}
// Cushion tops are teleportable islands: you can point-and-teleport straight
// onto a couch seat. (Seat waypoints land here via shouldLandWhenPossible.)
const CUSHION_TOP = 0.45;
for (const [cx, cz, w, d] of [
  [-0.44, couchA.z + 0.06], [0.44, couchA.z + 0.06],
  [-0.44, couchB.z - 0.06], [0.44, couchB.z - 0.06],
  ...couchC.cushions.map(([cx2, cz2]) => [cx2, cz2, 0.5, 0.72]), // TV couch (rotated)
  ...DESK_CHAIRS.map(([, cx2, cz2]) => [cx2, cz2, 0.4, 0.4]), // desk chair seats
  ...STOOLS.map(([, sx, sz]) => [sx, sz, 0.4, 0.4]) // kitchen stool seats
]) {
  const gm = new THREE.PlaneGeometry(w || 0.72, d || 0.5);
  gm.rotateX(-Math.PI / 2);
  // Land at FLOOR level inside the seat footprint: a physically-seated player
  // (real HMD at sitting height) then reads as seated in the couch/chair.
  // Cushion-height islands put avatars standing ON the cushions ("hovering").
  gm.translate(cx, 0.002, cz);
  navGeoms.push(gm);
}
const navMesh = new THREE.Mesh(mergeGeometries(navGeoms), mat(0x00ff00));
navMesh.name = "NavMesh";
scene.add(navMesh);

// ---------------------------------------------------------------------------
// Spawn points + seat waypoints + light anchors (empty nodes; components
// injected post-export). Seats face the opposite couch.
// ---------------------------------------------------------------------------
function empty(name, x, y, z, ry) {
  const o = new THREE.Object3D();
  o.name = name;
  o.position.set(x, y, z);
  if (ry !== undefined) o.rotation.y = ry;
  scene.add(o);
  return o;
}
// Spawned avatars face the waypoint's +z axis (verified by raycast test).
empty("Spawn_1", -1.9, 0, -2.15, 0); // north-west corner, facing into the room (+z)
empty("Spawn_2", 1.9, 0, 2.15, Math.PI); // south-east corner, facing into the room (-z)
// Seat waypoints float above the cushions so their icons are visible and
// clickable (an icon at floor level ends up buried inside the couch base).
// The character controller lands on the cushion nav-mesh island after travel.
const SEAT_Y = 0.55;
empty("Seat_A1", couchA.cushionX[0], SEAT_Y, couchA.z + 0.06, Math.PI); // couch A faces -z → yaw PI
empty("Seat_A2", couchA.cushionX[1], SEAT_Y, couchA.z + 0.06, Math.PI);
empty("Seat_B1", couchB.cushionX[0], SEAT_Y, couchB.z - 0.06, 0);
empty("Seat_B2", couchB.cushionX[1], SEAT_Y, couchB.z - 0.06, 0);
// TV couch waypoints: face the wall TV (-x → yaw -PI/2)
empty("Seat_C1", couchC.cushions[0][0], SEAT_Y, couchC.cushions[0][1], -Math.PI / 2);
empty("Seat_C2", couchC.cushions[1][0], SEAT_Y, couchC.cushions[1][1], -Math.PI / 2);
// Desk chair waypoints: icon floats above the seat, avatar faces the monitor.
for (const [tag, cx, cz, yaw] of DESK_CHAIRS) empty(`Seat_${tag}`, cx, 0.6, cz, yaw);
// Kitchen stool waypoints: avatar faces the island/kitchen (+x → yaw PI/2).
for (const [tag, sx, sz] of STOOLS) empty(`Seat_${tag}`, sx, 0.8, sz, Math.PI / 2);
empty("AmbientLight", CX, H - 0.4, 0);

// ---------------------------------------------------------------------------
// Hubs component map (node name → MOZ_hubs_components)
// ---------------------------------------------------------------------------
const seatWaypoint = id => ({
  networked: { id },
  waypoint: {
    canBeSpawnPoint: false,
    canBeOccupied: true,
    canBeClicked: true,
    willDisableMotion: true,
    willDisableTeleporting: false,
    snapToNavMesh: false,
    willMaintainInitialOrientation: false,
    willMaintainWorldUp: true,
    isOccupied: false
  }
});
const pointLight = (intensity, range) => ({
  "point-light": {
    color: "#ffc98c",
    intensity,
    range,
    decay: 2,
    castShadow: false,
    shadowMapResolution: [512, 512],
    shadowBias: 0,
    shadowRadius: 1
  }
});
const HUBS_COMPONENTS = {
  NavMesh: { "nav-mesh": {}, visible: { visible: false } },
  Spawn_1: { "spawn-point": {} },
  Spawn_2: { "spawn-point": {} },
  Seat_A1: seatWaypoint("seat-a1"),
  Seat_A2: seatWaypoint("seat-a2"),
  Seat_B1: seatWaypoint("seat-b1"),
  Seat_B2: seatWaypoint("seat-b2"),
  Seat_C1: seatWaypoint("seat-c1"),
  Seat_C2: seatWaypoint("seat-c2"),
  Seat_K1: seatWaypoint("seat-k1"),
  Seat_K2: seatWaypoint("seat-k2"),
  Seat_S1: seatWaypoint("seat-s1"),
  Seat_S2: seatWaypoint("seat-s2"),
  Seat_S3: seatWaypoint("seat-s3"),
  LampC_Light: pointLight(1.4, 7),
  LampD_Light: pointLight(1.4, 7),
  AmbientLight: { "ambient-light": { color: "#ffe2c4", intensity: 0.55 } }
};

// ---------------------------------------------------------------------------
// Export GLB, then inject MOZ_hubs_components into the JSON chunk.
// ---------------------------------------------------------------------------
const exporter = new GLTFExporter();
const glb = await new Promise((resolve, reject) =>
  exporter.parse(scene, resolve, reject, { binary: true })
);

const buf = Buffer.from(glb);
const jsonLen = buf.readUInt32LE(12);
const json = JSON.parse(buf.subarray(20, 20 + jsonLen).toString("utf8"));
let binChunk = buf.subarray(20 + jsonLen); // includes its 8-byte chunk header

// --- Embed photo textures into the GLB binary chunk:
// ---  * Central Park view (Top of the Rock, CC BY 2.0) -> emissive backdrop
// ---    placeholder; view-switcher.js swaps in the full-res views at runtime.
{
  const { readFileSync } = await import("fs");
  const REPEAT = 10497, CLAMP = 33071;
  const EMBEDS = [
    { file: "./centralpark-wide.jpg", material: "RockiesBackdrop", slot: "emissive", wrap: CLAMP }
  ];

  let binData = Buffer.from(binChunk.subarray(8, 8 + binChunk.readUInt32LE(0)));
  json.bufferViews = json.bufferViews || [];
  json.images = json.images || [];
  json.samplers = json.samplers || [];
  json.textures = json.textures || [];

  for (const e of EMBEDS) {
    const img = readFileSync(new URL(e.file, import.meta.url));
    const pad = (4 - (binData.length % 4)) % 4;
    const offset = binData.length + pad;
    binData = Buffer.concat([binData, Buffer.alloc(pad), img]);
    json.bufferViews.push({ buffer: 0, byteOffset: offset, byteLength: img.length });
    json.images.push({ bufferView: json.bufferViews.length - 1, mimeType: "image/jpeg" });
    json.samplers.push({ magFilter: 9729, minFilter: 9987, wrapS: e.wrap, wrapT: e.wrap });
    json.textures.push({ sampler: json.samplers.length - 1, source: json.images.length - 1 });
    const texIndex = json.textures.length - 1;

    const m = (json.materials || []).find(mm => mm.name === e.material);
    if (!m) throw new Error(`${e.material} material not found in export`);
    if (e.slot === "emissive") {
      m.emissiveTexture = { index: texIndex };
      m.emissiveFactor = [1, 1, 1];
      m.pbrMetallicRoughness = { ...(m.pbrMetallicRoughness || {}), baseColorFactor: [0, 0, 0, 1] };
    } else {
      m.pbrMetallicRoughness = {
        ...(m.pbrMetallicRoughness || {}),
        baseColorTexture: { index: texIndex },
        baseColorFactor: [1, 1, 1, 1]
      };
    }
  }

  const endPad = (4 - (binData.length % 4)) % 4;
  binData = Buffer.concat([binData, Buffer.alloc(endPad)]);
  const newBinHeader = Buffer.alloc(8);
  newBinHeader.writeUInt32LE(binData.length, 0);
  newBinHeader.writeUInt32LE(0x004e4942, 4); // 'BIN'
  binChunk = Buffer.concat([newBinHeader, binData]);
  json.buffers[0].byteLength = binData.length;
}

json.extensionsUsed = [...new Set([...(json.extensionsUsed || []), "MOZ_hubs_components"])];
json.extensions = { ...(json.extensions || {}), MOZ_hubs_components: { version: 4 } };
let tagged = 0;
for (const node of json.nodes || []) {
  const comps = HUBS_COMPONENTS[node.name];
  if (comps) {
    node.extensions = { ...(node.extensions || {}), MOZ_hubs_components: comps };
    tagged++;
  }
}
if (tagged !== Object.keys(HUBS_COMPONENTS).length) {
  const found = (json.nodes || []).map(n => n.name);
  const missing = Object.keys(HUBS_COMPONENTS).filter(k => !found.includes(k));
  throw new Error(`Only tagged ${tagged} nodes; missing: ${missing.join(", ")}`);
}

let jsonOut = Buffer.from(JSON.stringify(json), "utf8");
const pad = (4 - (jsonOut.length % 4)) % 4;
if (pad) jsonOut = Buffer.concat([jsonOut, Buffer.alloc(pad, 0x20)]);
const header = Buffer.alloc(12);
header.write("glTF", 0);
header.writeUInt32LE(2, 4);
header.writeUInt32LE(12 + 8 + jsonOut.length + binChunk.length, 8);
const jsonHeader = Buffer.alloc(8);
jsonHeader.writeUInt32LE(jsonOut.length, 0);
jsonHeader.writeUInt32LE(0x4e4f534a, 4); // 'JSON'
writeFileSync(out, Buffer.concat([header, jsonHeader, jsonOut, binChunk]));

const stats = { nodes: json.nodes.length, meshes: (json.meshes || []).length, tagged, bytes: 12 + 8 + jsonOut.length + binChunk.length };
console.log(`Wrote ${out}:`, JSON.stringify(stats));
