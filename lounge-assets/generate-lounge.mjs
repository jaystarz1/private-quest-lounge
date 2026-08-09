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
  floor: mat(0x7a5537, { roughness: 0.85 }),
  logWall: new THREE.MeshStandardMaterial({ name: "LogWall", color: 0xffffff, roughness: 0.92, metalness: 0 }),
  wall: mat(0xe6dac2, { roughness: 0.95 }),
  ceiling: mat(0xf0e8d8, { roughness: 0.95 }),
  trim: mat(0x5c4330, { roughness: 0.8 }),
  couchA: mat(0x9c4a38, { roughness: 0.9 }), // terracotta
  couchB: mat(0x4a6351, { roughness: 0.9 }), // sage green
  cushionA: mat(0xb85c46, { roughness: 0.95 }),
  cushionB: mat(0x5c7a64, { roughness: 0.95 }),
  throw1: mat(0xd9a441, { roughness: 0.95 }),
  throw2: mat(0xc8b89a, { roughness: 0.95 }),
  wood: mat(0x4e3826, { roughness: 0.7 }),
  rug: mat(0xa85f42, { roughness: 1.0 }),
  rugInner: mat(0xc07a52, { roughness: 1.0 }),
  lampShade: new THREE.MeshStandardMaterial({
    color: 0xffd9a0,
    emissive: 0xffc98c,
    emissiveIntensity: 1.6,
    roughness: 0.9
  }),
  lampMetal: mat(0x3a3128, { roughness: 0.5, metalness: 0.6 }),
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
  frame: mat(0x2e2620, { roughness: 0.6 }),
  art1a: mat(0xc46a4a, { roughness: 0.9 }),
  art1b: mat(0xe0b075, { roughness: 0.9 }),
  art2a: mat(0x51707e, { roughness: 0.9 }),
  art2b: mat(0xa8b8a0, { roughness: 0.9 }),
  book: mat(0x7e3b32, { roughness: 0.9 }),
  mug: mat(0xdac8a8, { roughness: 0.7 }),
  plantPot: mat(0xb0603f, { roughness: 0.9 }),
  plant: mat(0x3f6b3a, { roughness: 0.95 })
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
// The whole north wall is floor-to-ceiling glass with a Canadian Rockies
// valley (Moraine Lake, public domain) as the view.
// ---------------------------------------------------------------------------
const X_MIN = -9, X_MAX = 3, Z_MIN = -5, Z_MAX = 5;
const W = X_MAX - X_MIN, D = Z_MAX - Z_MIN, T = 0.12; // wall thickness
const H = 3;        // south-wall height
const H_N = 4.5;    // glass-wall height (5 ft higher); roof slopes up to it
const CX = (X_MIN + X_MAX) / 2, CZ = (Z_MIN + Z_MAX) / 2;
const LOG_PERIOD = 1.8; // metres of wall per texture tile (~6 logs)
box("Floor", W, T, D, M.floor, CX, -T / 2, CZ);
// Sloped timber roof rising from the south wall (3 m) to the glass wall (4.5 m)
const slope = Math.atan((H_N - H) / D);
const roof = box("Roof", W, T, D / Math.cos(slope) + 0.2, mat(0x8a6242, { roughness: 0.85 }), CX, (H + H_N) / 2 + T / 2, CZ);
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
function couch(tag, z, facing, bodyMat, cushMat, throwMat) {
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
  g.position.set(0, 0, z);
  scene.add(g);
  return { seatH, cushionX: [-0.44, 0.44], z };
}
const couchA = couch("A", 1.55, -1, M.couchA, M.cushionA, M.throw1); // faces the window
const couchB = couch("B", -1.55, 1, M.couchB, M.cushionB, M.throw2);

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
lamp("L", -2.45, -1.9);
lamp("R", 2.45, 1.9);
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
art("East", X_MAX - 0.03, 0.4, -Math.PI / 2, M.art1a, M.art1b);
art("West", X_MIN + 0.03, -0.4, Math.PI / 2, M.art2a, M.art2b);

// Plant in the corner
cyl("Plant_Pot", 0.16, 0.12, 0.28, M.plantPot, 2.5, 0.14, -2.0);
cyl("Plant_Leaves", 0.02, 0.28, 0.75, M.plant, 2.5, 0.75, -2.0, 8);

// ---------------------------------------------------------------------------
// Nav mesh: walkable floor minus furniture footprints. Single merged mesh.
// Rectangles: [x1, z1, x2, z2]
// ---------------------------------------------------------------------------
const walkRects = [
  [-8.85, -4.85, 2.85, -2.05], // north area (by the glass wall)
  [-8.85, 2.05, 2.85, 4.85],   // south area
  [-8.85, -2.05, -1.15, 2.05], // western extension
  [1.15, -2.05, 2.85, 2.05],   // east corridor
  [-1.15, -1.05, 1.15, -0.45], // between couch B and table
  [-1.15, 0.45, 1.15, 1.05]    // between table and couch A
];
const navGeoms = walkRects.map(([x1, z1, x2, z2]) => {
  const gm = new THREE.PlaneGeometry(x2 - x1, z2 - z1);
  gm.rotateX(-Math.PI / 2);
  gm.translate((x1 + x2) / 2, 0.002, (z1 + z2) / 2);
  return gm;
});
// Cushion tops are teleportable islands: you can point-and-teleport straight
// onto a couch seat. (Seat waypoints land here via shouldLandWhenPossible.)
const CUSHION_TOP = 0.45;
for (const [cx, cz] of [
  [-0.44, couchA.z + 0.06], [0.44, couchA.z + 0.06],
  [-0.44, couchB.z - 0.06], [0.44, couchB.z - 0.06]
]) {
  const gm = new THREE.PlaneGeometry(0.72, 0.5);
  gm.rotateX(-Math.PI / 2);
  gm.translate(cx, CUSHION_TOP + 0.005, cz);
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
  LampL_Light: pointLight(1.4, 7),
  LampR_Light: pointLight(1.4, 7),
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
// ---  * Rockies view (Moraine Lake, public domain) -> emissive backdrop
// ---  * Log wall (Poly Haven beam_wall_01, CC0, warmed) -> tiling base colour
{
  const { readFileSync } = await import("fs");
  const REPEAT = 10497, CLAMP = 33071;
  const EMBEDS = [
    { file: "./rockies-wide.jpg", material: "RockiesBackdrop", slot: "emissive", wrap: CLAMP },
    { file: "./logwall.jpg", material: "LogWall", slot: "base", wrap: REPEAT }
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
