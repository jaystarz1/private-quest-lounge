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

// ---------------------------------------------------------------------------
// Room shell: 6 wide (x) x 5 deep (z) x 3 high. Window on the -z wall.
// ---------------------------------------------------------------------------
const W = 6, D = 5, H = 3, T = 0.12; // wall thickness
box("Floor", W, T, D, M.floor, 0, -T / 2, 0);
box("Ceiling", W, T, D, M.ceiling, 0, H + T / 2, 0);
box("Wall_East", T, H, D, M.wall, W / 2 + T / 2, H / 2, 0);
box("Wall_West", T, H, D, M.wall, -W / 2 - T / 2, H / 2, 0);
box("Wall_South", W + 2 * T, H, T, M.wall, 0, H / 2, D / 2 + T / 2);

// North wall with window opening (2.2 x 1.4, sill at 0.95)
const winW = 2.2, winH = 1.4, sill = 0.95;
const nz = -D / 2 - T / 2;
box("Wall_North_L", (W - winW) / 2 + 2 * T, H, T, M.wall, -(winW / 2 + (W - winW) / 4 + T), H / 2, nz);
box("Wall_North_R", (W - winW) / 2 + 2 * T, H, T, M.wall, winW / 2 + (W - winW) / 4 + T, H / 2, nz);
box("Wall_North_Bottom", winW, sill, T, M.wall, 0, sill / 2, nz);
box("Wall_North_Top", winW, H - sill - winH, T, M.wall, 0, (H + sill + winH) / 2, nz);
// Window frame + night glass
box("WindowFrame_B", winW + 0.16, 0.08, 0.16, M.trim, 0, sill - 0.04, nz);
box("WindowFrame_T", winW + 0.16, 0.08, 0.16, M.trim, 0, sill + winH + 0.04, nz);
box("WindowFrame_L", 0.08, winH + 0.16, 0.16, M.trim, -winW / 2 - 0.04, sill + winH / 2, nz);
box("WindowFrame_R", 0.08, winH + 0.16, 0.16, M.trim, winW / 2 + 0.04, sill + winH / 2, nz);
box("WindowFrame_Mid", 0.05, winH, 0.14, M.trim, 0, sill + winH / 2, nz);
const glass = box("NightGlass", winW, winH, 0.02, M.nightGlass, 0, sill + winH / 2, nz + 0.02);
glass.name = "NightGlass";
const moon = new THREE.Mesh(new THREE.CircleGeometry(0.13, 20), M.moon);
moon.name = "Moon";
moon.position.set(0.6, sill + winH - 0.32, nz + 0.035);
scene.add(moon);
// RainFX: a quad the client animates with a cheap shader (kept invisible-ish here)
const rain = box("RainFX", winW, winH, 0.005, M.nightGlass.clone(), 0, sill + winH / 2, nz + 0.045);
rain.material.transparent = true;
rain.material.opacity = 0.25;

// Skirting
box("Skirt_S", W, 0.1, 0.03, M.trim, 0, 0.05, D / 2 - 0.015);
box("Skirt_E", 0.03, 0.1, D, M.trim, W / 2 - 0.015, 0.05, 0);
box("Skirt_W", 0.03, 0.1, D, M.trim, -W / 2 + 0.015, 0.05, 0);

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
art("East", W / 2 - 0.03, 0.4, -Math.PI / 2, M.art1a, M.art1b);
art("West", -W / 2 + 0.03, -0.4, Math.PI / 2, M.art2a, M.art2b);

// Plant in the corner
cyl("Plant_Pot", 0.16, 0.12, 0.28, M.plantPot, 2.5, 0.14, -2.0);
cyl("Plant_Leaves", 0.02, 0.28, 0.75, M.plant, 2.5, 0.75, -2.0, 8);

// ---------------------------------------------------------------------------
// Nav mesh: walkable floor minus furniture footprints. Single merged mesh.
// Rectangles: [x1, z1, x2, z2]
// ---------------------------------------------------------------------------
const walkRects = [
  [-2.8, -2.3, 2.8, -2.05], // north strip (window side)
  [-2.8, 2.05, 2.8, 2.3],   // south strip
  [-2.8, -2.05, -1.15, 2.05], // west corridor
  [1.15, -2.05, 2.8, 2.05],   // east corridor
  [-1.15, -1.05, 1.15, -0.45], // between couch B and table
  [-1.15, 0.45, 1.15, 1.05]    // between table and couch A
];
const navGeoms = walkRects.map(([x1, z1, x2, z2]) => {
  const gm = new THREE.PlaneGeometry(x2 - x1, z2 - z1);
  gm.rotateX(-Math.PI / 2);
  gm.translate((x1 + x2) / 2, 0.002, (z1 + z2) / 2);
  return gm;
});
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
empty("Spawn_1", -1.9, 0, -2.15, Math.PI); // by the window, facing the room... ry set below
empty("Spawn_2", 1.9, 0, 2.15, 0);
// Seat waypoints: y is tunable (0 = floor height at cushion centre).
const SEAT_Y = 0;
empty("Seat_A1", couchA.cushionX[0], SEAT_Y, couchA.z + 0.06, Math.PI); // couch A faces -z → yaw PI
empty("Seat_A2", couchA.cushionX[1], SEAT_Y, couchA.z + 0.06, Math.PI);
empty("Seat_B1", couchB.cushionX[0], SEAT_Y, couchB.z - 0.06, 0);
empty("Seat_B2", couchB.cushionX[1], SEAT_Y, couchB.z - 0.06, 0);
empty("AmbientLight", 0, H - 0.4, 0);

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
  Moon: pointLight(0.4, 4),
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
const binChunk = buf.subarray(20 + jsonLen); // includes its 8-byte chunk header

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
