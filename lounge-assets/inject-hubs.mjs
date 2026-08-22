// Injects MOZ_hubs_components into a GLB produced by build-penthouse.py.
// Tags NavMesh, spawn points, seat waypoints and lights by node name, and
// forces the RockiesBackdrop material emissive so view-switcher.js can swap
// the window view via emissiveMap.
//
// Usage: node inject-hubs.mjs <in.glb> <out.glb>
import { readFileSync, writeFileSync } from "fs";

const [inFile, outFile] = process.argv.slice(2);
const buf = readFileSync(inFile);
if (buf.readUInt32LE(0) !== 0x46546c67) throw new Error("not a GLB");
const jsonLen = buf.readUInt32LE(12);
const json = JSON.parse(buf.subarray(20, 20 + jsonLen).toString("utf8"));
const binChunk = buf.subarray(20 + jsonLen);

const seatWaypoint = (id, eyeHeight = 1.6) => ({
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
    eyeHeight,
    isOccupied: false
  }
});
const pointLight = (intensity, range) => ({
  "point-light": {
    color: "#ffe3c0",
    intensity,
    range,
    decay: 2,
    castShadow: false,
    shadowMapResolution: [512, 512],
    shadowBias: 0,
    shadowRadius: 1
  }
});
// Pattern-based tagging: any Seat_* empty becomes an occupiable
// waypoint, Spawn_* a spawn point, and selected Light_* nodes as warm point
// lights. Quest renders every point light against many materials, so four
// broad fixtures plus ambient light are the stability budget for this scene.
// Blender build script is the single source of truth for what exists.
const LIGHTS = {
  Light_A: [1.3, 10], // lower floor west
  Light_C: [1.2, 10], // lower floor east
  Light_G: [1.0, 9], // sky den
  Light_H: [1.1, 9] // elevator lobby
};

json.extensionsUsed = [...new Set([...(json.extensionsUsed || []), "MOZ_hubs_components"])];
json.extensions = { ...(json.extensions || {}), MOZ_hubs_components: { version: 4 } };
const counts = { nav: 0, spawn: 0, seat: 0, light: 0, ambient: 0 };
for (const node of json.nodes || []) {
  const n = node.name || "";
  let comps = null;
  if (/^Light_/.test(n) && node.extensions?.MOZ_hubs_components?.["point-light"]) {
    delete node.extensions.MOZ_hubs_components["point-light"];
  }
  if (n === "NavMesh") {
    comps = { "nav-mesh": {}, visible: { visible: false } };
    counts.nav++;
  } else if (/^Spawn_/.test(n)) {
    comps = { "spawn-point": {} };
    counts.spawn++;
  } else if (/^Seat_/.test(n)) {
    const eyeHeight = /^Seat_HotTub_/.test(n) ? 0.70 : /^Seat_Bed_/.test(n) ? 0.80 : 1.6;
    comps = seatWaypoint(n.toLowerCase().replace(/_/g, "-"), eyeHeight);
    counts.seat++;
  } else if (n === "AmbientLight") {
    comps = { "ambient-light": { color: "#ffe8d2", intensity: 0.6 } };
    counts.ambient++;
  } else if (LIGHTS[n]) {
    comps = pointLight(...LIGHTS[n]);
    counts.light++;
  }
  if (comps) node.extensions = { ...(node.extensions || {}), MOZ_hubs_components: comps };
}
const tagged = counts.nav + counts.spawn + counts.seat + counts.light + counts.ambient;
console.log("tag counts:", JSON.stringify(counts));
if (counts.nav !== 1 || counts.spawn !== 2 || counts.seat < 45 || counts.light !== 4 || counts.ambient !== 1) {
  throw new Error(`unexpected tag counts: ${JSON.stringify(counts)}`);
}
const pianoNodes = (json.nodes || []).filter(node => /^(Piano|Seat_Pno)/.test(node.name || ""));
if (pianoNodes.length) throw new Error(`piano nodes remain after removal: ${pianoNodes.map(node => node.name)}`);
const bedSeatNodes = (json.nodes || []).filter(node => /^Seat_Bed_/.test(node.name || ""));
if (
  bedSeatNodes.length !== 6 ||
  bedSeatNodes.some(
    node =>
      node.extensions?.MOZ_hubs_components?.waypoint?.willMaintainWorldUp !== true ||
      node.extensions?.MOZ_hubs_components?.waypoint?.eyeHeight !== 0.80
  )
) {
  throw new Error("six upright bed seats with 0.80 m seated eye height are required");
}
const hotTubSeatNodes = (json.nodes || []).filter(node => /^Seat_HotTub_/.test(node.name || ""));
if (hotTubSeatNodes.length !== 4) throw new Error(`expected four hot-tub seats, found ${hotTubSeatNodes.length}`);
for (const node of hotTubSeatNodes) {
  if (node.extensions?.MOZ_hubs_components?.waypoint?.eyeHeight !== 0.70) {
    throw new Error(`${node.name} is missing its 0.70 m seated eye height`);
  }
  // glTF Y is Blender Z. With the 0.70 m seated eye height and the client's
  // 0.15 m occupied-waypoint lift, the final eye line is 1.10 m, 0.545 m
  // above the water. The avatar rig is sunk so the body is seated, not standing.
  const targetHeight = node.translation?.[1];
  if (targetHeight === undefined || Math.abs(targetHeight - 0.25) > 0.01) {
    throw new Error(`${node.name} has unsafe hot-tub target height ${targetHeight}`);
  }
}
// Every backdrop plane must exist so no window faces a void.
for (const req of ["RockiesView", "ViewEast", "ViewWest", "ViewSouth"]) {
  if (!(json.nodes || []).some(nd => nd.name === req)) throw new Error(`missing backdrop plane ${req}`);
}

// Each directional backdrop material must be emissive with an emissiveTexture
// (the runtime view switcher swaps each wall's emissiveMap independently).
for (const mn of ["RockiesBackdrop", "EastBackdrop", "WestBackdrop", "SouthBackdrop"]) {
  const m = (json.materials || []).find(mm => mm.name === mn);
  if (!m) throw new Error(`${mn} material not found`);
  if (!m.emissiveTexture) throw new Error(`${mn} has no emissiveTexture — check Blender emission export`);
  m.emissiveFactor = [1, 1, 1];
  if (m.pbrMetallicRoughness) m.pbrMetallicRoughness.baseColorFactor = [0, 0, 0, 1];
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
jsonHeader.writeUInt32LE(0x4e4f534a, 4);
writeFileSync(outFile, Buffer.concat([header, jsonHeader, jsonOut, binChunk]));
console.log(`Wrote ${outFile}: tagged ${tagged} nodes`);
