// Tags the Mouth node of an avatar GLB with the Hubs scale-audio-feedback
// component (mouth pulses with the wearer's voice). Blender's exporter can't
// write MOZ_hubs_components, so this is a post-export step.
// Run: node tag-mouth.mjs <avatar.glb>
import fs from "fs";

const file = process.argv[2];
if (!file) {
  console.error("usage: node tag-mouth.mjs <avatar.glb>");
  process.exit(1);
}

const buf = fs.readFileSync(file);
const jsonLen = buf.readUInt32LE(12);
const gltf = JSON.parse(buf.slice(20, 20 + jsonLen).toString());

const mouth = gltf.nodes.find(n => n.name === "Mouth");
if (!mouth) {
  console.error("no Mouth node in", file);
  process.exit(1);
}
mouth.extensions = mouth.extensions || {};
mouth.extensions.MOZ_hubs_components = {
  "scale-audio-feedback": { minScale: 1, maxScale: 1.6 }
};
gltf.extensionsUsed = Array.from(new Set([...(gltf.extensionsUsed || []), "MOZ_hubs_components"]));

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
console.log("tagged Mouth in", file);
