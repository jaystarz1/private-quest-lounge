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
  Light_G: [1.3, 12], // Rovers bar, sky den above it, roof terrace
  Light_H: [0.9, 8] // den banker's lamp (also reaches the spa)
};

json.extensionsUsed = [...new Set([...(json.extensionsUsed || []), "MOZ_hubs_components"])];
json.extensions = { ...(json.extensions || {}), MOZ_hubs_components: { version: 4 } };
const counts = { nav: 0, spawn: 0, seat: 0, light: 0, ambient: 0, mirror: 0, figures: 0 };
const metaNode = (json.nodes || []).find(nd => /^DinnerMeta_L\d+_W\d+_P\d+$/.test(nd.name || ""));
if (!metaNode) throw new Error("DinnerMeta_* node missing (dinner_figures.py names the linger window)");
const [, metaAt, metaLen, metaPhase] = metaNode.name.match(/^DinnerMeta_L(\d+)_W(\d+)_P(\d+)$/);
const DINNER_META = { at: Number(metaAt) / 1000, len: Number(metaLen), phase: Number(metaPhase) };
console.log("dinner linger:", JSON.stringify(DINNER_META));
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
    // Every seat waypoint sits ON its cushion/mattress surface (build-penthouse.py
    // ray-casts the seat top), so a seated eye line is surface + eyeHeight +
    // the client's 0.15 m occupied lift: 0.75 m above the seat, like a person.
    // Hot-tub seats are sunk below the water line and keep their own value.
    const eyeHeight = /^Seat_HotTub_/.test(n) ? 0.70 : 0.60;
    comps = seatWaypoint(n.toLowerCase().replace(/_/g, "-"), eyeHeight);
    counts.seat++;
  } else if (/^Mirror_/.test(n)) {
    // Real reflecting mirror (client Reflector, renders the scene again from
    // the mirrored camera, so keep to one per room). The node's scale is the
    // mirror's width and height; it faces the node's +Z.
    comps = { mirror: { color: "#a8adb2" } };
    counts.mirror++;
  } else if (/^Fig_[A-Za-z]+$/.test(n) && node.mesh === undefined) {
    // Rovers regulars and the NE bed couple (rovers_figures.py): each armature
    // loops its own clip, found by name. serverClock pins every clip to the
    // shared server clock, so all headsets see the same moment whenever they
    // joined, and clips sharing a length (the bar group) stay in step.
    // The dinner party and its prop rig (Fig_Din*, dinner_figures.py) have two
    // clips: the dinner plays once from the start of the room session (the
    // earliest joiner still present), then the lounge clip loops.
    // dinner_figures.py names an empty DinnerMeta_L<ms>_W<s>_P<s>: the linger
    // window the client may cut short and the phase the evening locks to.
    comps = /^Fig_Din/.test(n)
      ? { "loop-animation": { clip: `${n}Dinner,${n}Lounge`, paused: false, serverClock: true, session: true,
                              lingerAt: DINNER_META.at, lingerLen: DINNER_META.len, phase: DINNER_META.phase },
          frustrum: { culled: false } }
      : { "loop-animation": { clip: `${n}Loop`, paused: false, serverClock: true }, frustrum: { culled: false } };
    counts.figures++;
  } else if (n === "AmbientLight") {
    comps = { "ambient-light": { color: "#ffe8d2", intensity: 0.6 } };
    counts.ambient++;
  } else if (LIGHTS[n]) {
    comps = pointLight(...LIGHTS[n]);
    counts.light++;
  }
  if (comps) node.extensions = { ...(node.extensions || {}), MOZ_hubs_components: comps };
}
// figures: 28 + the hot tub (TubA/B/S, TubBall) + the café (DinMime, DinCafA/B, DinCafeProps)
const tagged = counts.nav + counts.spawn + counts.seat + counts.light + counts.ambient + counts.mirror + counts.figures;
console.log("tag counts:", JSON.stringify(counts));
if (counts.nav !== 1 || counts.spawn !== 2 || counts.seat < 40 || counts.light !== 4 || counts.ambient !== 1 || counts.mirror !== 1 || counts.figures !== 36) {
  throw new Error(`unexpected tag counts: ${JSON.stringify(counts)}`);
}
// Every figure needs its own clip, and the bar group (barman + three
// regulars) must share one length so their glass hand-offs stay in step.
const anims = json.animations || [];
const figNodes = (json.nodes || []).filter(nd => /^Fig_[A-Za-z]+$/.test(nd.name || "") && nd.mesh === undefined);
const clipLen = name => {
  const a = anims.find(an => an.name === name);
  return a && Math.max(...a.samplers.map(sm => json.accessors[sm.input].max[0]));
};
const clipsOf = name => (/^Fig_Din/.test(name) ? [`${name}Dinner`, `${name}Lounge`] : [`${name}Loop`]);
let clipCount = 0;
for (const nd of figNodes) {
  for (const c of clipsOf(nd.name)) {
    if (!clipLen(c)) throw new Error(`figure ${nd.name} has no clip ${c}`);
    clipCount++;
  }
  if (nd.extensions?.MOZ_hubs_components?.["loop-animation"]?.serverClock !== true) throw new Error(`figure ${nd.name} is not on the server clock`);
}
if (anims.length !== clipCount) throw new Error(`${anims.length} clips for ${clipCount} expected`);
// The evening is phase-locked to the Rovers: both dinner-party clips are whole
// phases long, the regulars loop on exactly one phase, and the linger window
// sits inside the dinner clip.
for (const nd of figNodes.filter(nd => /^Fig_Din/.test(nd.name))) {
  for (const c of clipsOf(nd.name)) {
    const len = clipLen(c), r = len / DINNER_META.phase;
    if (Math.abs(r - Math.round(r)) > 1e-3) throw new Error(`${c} is ${len}s, not whole phases of ${DINNER_META.phase}s`);
  }
  if (DINNER_META.at + DINNER_META.len > clipLen(`${nd.name}Dinner`) - 1) throw new Error("linger window past the dinner clip");
}
if (Math.abs(clipLen("Fig_BmLoop") - DINNER_META.phase) > 1e-3) throw new Error(`Rovers loop is not the dinner phase`);
const barLens = ["Fig_Bm", "Fig_BarA", "Fig_BarB", "Fig_BarC"].map(nm => clipLen(`${nm}Loop`));
if (barLens.some(len => Math.abs(len - barLens[0]) > 1e-4)) throw new Error(`bar group clip lengths differ: ${barLens}`);
// The unusable source piano (Object_108) must stay deleted; the procedural
// black-lacquer grand (Pno_*) that replaced it is expected.
if ((json.nodes || []).some(node => node.name === "Object_108")) throw new Error("source piano Object_108 still present");
if (!(json.nodes || []).some(node => node.name === "Pno_Body")) throw new Error("procedural piano missing");
const bedSeatNodes = (json.nodes || []).filter(node => /^Seat_Bed_/.test(node.name || ""));
if (
  bedSeatNodes.length !== 4 ||
  bedSeatNodes.some(
    node =>
      node.extensions?.MOZ_hubs_components?.waypoint?.willMaintainWorldUp !== true ||
      node.extensions?.MOZ_hubs_components?.waypoint?.eyeHeight !== 0.60
  )
) {
  throw new Error("four upright bed seats (NE bed taken by the couple) with 0.60 m seated eye height are required");
}
const hotTubSeatNodes = (json.nodes || []).filter(node => /^Seat_HotTub_/.test(node.name || ""));
// The south pair belongs to the animated hot tub regulars (rovers_figures.py).
if (hotTubSeatNodes.length !== 2) throw new Error(`expected two hot-tub seats, found ${hotTubSeatNodes.length}`);
for (const node of hotTubSeatNodes) {
  if (node.extensions?.MOZ_hubs_components?.waypoint?.eyeHeight !== 0.70) {
    throw new Error(`${node.name} is missing its 0.70 m seated eye height`);
  }
  // glTF Y is Blender Z. With the 0.70 m seated eye height and the client's
  // 0.15 m occupied-waypoint lift, the final eye line is 0.95 m, 0.40 m above
  // the water (z 0.555): chest-deep. The rig is sunk so the body is seated.
  const targetHeight = node.translation?.[1];
  if (targetHeight === undefined || Math.abs(targetHeight - 0.10) > 0.01) {
    throw new Error(`${node.name} has unsafe hot-tub target height ${targetHeight}`);
  }
}
// The skyline cylinder and sky dome must exist so no window faces a void.
for (const req of ["ViewPano", "ViewSky"]) {
  if (!(json.nodes || []).some(nd => nd.name === req)) throw new Error(`missing backdrop mesh ${req}`);
}

// Each backdrop material must be emissive with an emissiveTexture (the
// runtime view switcher swaps each emissiveMap for the day/dusk images).
for (const mn of ["PanoBackdrop", "SkyBackdrop"]) {
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
