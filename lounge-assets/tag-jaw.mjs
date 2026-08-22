// Tags every node whose mesh carries a jawOpen morph target with the Hubs
// morph-audio-feedback component, so the jaw opens with the wearer's voice.
// For MetaPerson avatars (skinned face, no separate mouth mesh) — the
// scale-audio-feedback Mouth-node trick only works on the low-poly avatars.
// Run: node tag-jaw.mjs <avatar.glb>
import fs from "fs";

const file = process.argv[2];
if (!file) {
  console.error("usage: node tag-jaw.mjs <avatar.glb>");
  process.exit(1);
}

const buf = fs.readFileSync(file);
const jsonLen = buf.readUInt32LE(12);
const gltf = JSON.parse(buf.slice(20, 20 + jsonLen).toString());

let tagged = 0;
for (const node of gltf.nodes) {
  if (node.mesh === undefined) continue;
  const mesh = gltf.meshes[node.mesh];
  const names = mesh.extras?.targetNames || [];
  if (!names.includes("jawOpen")) continue;
  node.extensions = node.extensions || {};
  node.extensions.MOZ_hubs_components = {
    ...node.extensions.MOZ_hubs_components,
    "morph-audio-feedback": { name: "jawOpen", minValue: 0, maxValue: 1.2 }
  };
  tagged++;
  console.log("tagged", node.name || `node[mesh ${node.mesh}]`);
}
if (!tagged) {
  console.error("no jawOpen meshes in", file);
  process.exit(1);
}
gltf.extensionsUsed = Array.from(new Set([...(gltf.extensionsUsed || []), "MOZ_hubs_components"]));
gltf.extensions = gltf.extensions || {};
gltf.extensions.MOZ_hubs_components = {
  ...gltf.extensions.MOZ_hubs_components,
  version: 4
};

let json = Buffer.from(JSON.stringify(gltf));
const pad = (4 - (json.length % 4)) % 4;
if (pad) json = Buffer.concat([json, Buffer.alloc(pad, 0x20)]);

const rest = buf.slice(20 + jsonLen); // remaining chunks (BIN)
const header = Buffer.alloc(20);
header.write("glTF", 0);
header.writeUInt32LE(2, 4);
header.writeUInt32LE(20 + json.length + rest.length, 8);
header.writeUInt32LE(json.length, 12);
header.writeUInt32LE(0x4e4f534a, 16); // 'JSON'

fs.writeFileSync(file, Buffer.concat([header, json, rest]));
console.log("tagged", tagged, "nodes in", file);
