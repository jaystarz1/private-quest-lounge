// Generates the preloaded avatar set for private-quest-lounge: six lightweight
// half-body human avatars (head, torso, hands — no legs, the VR-social norm).
// Bone hierarchy and proportions copied from upstream DefaultAvatar.glb so the
// stock ik-controller drives them unmodified:
//   AvatarRoot > Hips > Spine > (Neck > Head > LeftEye/RightEye, LeftHand, RightHand)
// Meshes are rigid-parented to bones (no skinning — cheaper on Quest).
// A "Mouth" node under Head carries scale-audio-feedback for talk movement.
//
// Usage: node generate-avatars.mjs [outdir]

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
import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";

const outdir = process.argv[2] || "avatars";
mkdirSync(outdir, { recursive: true });

// Upstream DefaultAvatar.glb rest-pose translations (verified 2026-08-08).
const BONE_T = {
  Hips: [0, 0, 0],
  Spine: [0, 0.33, 0],
  Neck: [0, 0.1435, 0],
  Head: [0, 0.0905, 0],
  LeftEye: [0.0614, 0.0595, 0.1309],
  RightEye: [-0.0614, 0.0595, 0.1309],
  LeftHand: [0.658, 0, 0],
  RightHand: [-0.658, 0, 0]
};

const VARIANTS = [
  { id: "amber", skin: 0xf0c8a4, hair: 0x3a2a1e, hairStyle: "short", shirt: 0xa8543a },
  { id: "sage", skin: 0xc68a5c, hair: 0x14100c, hairStyle: "bun", shirt: 0x5c7a64 },
  { id: "marigold", skin: 0x6f4530, hair: 0x0f0c0a, hairStyle: "short", shirt: 0xc99a3f },
  { id: "teal", skin: 0xf0c8a4, hair: 0x6e3a22, hairStyle: "long", shirt: 0x3f6e7a },
  { id: "indigo", skin: 0xc68a5c, hair: 0x9a9a94, hairStyle: "short", shirt: 0x3a4a6e },
  { id: "plum", skin: 0x6f4530, hair: 0x1a1412, hairStyle: "curly", shirt: 0x6e3a5c },
  { id: "slate", skin: 0xf0c8a4, hair: 0xb8b8b2, hairStyle: "short", beard: 0xa8a8a0, shirt: 0x4a5560 },
  { id: "rust", skin: 0xe8bc94, hair: 0x2a1c12, hairStyle: "bald", beard: 0x2a1c12, shirt: 0x8a4a32 },
  { id: "forest", skin: 0xf0c8a4, hair: 0x5c4330, hairStyle: "short", glasses: true, shirt: 0x3d5c3a },
  { id: "wine", skin: 0xc68a5c, hair: 0x1a1210, hairStyle: "long", glasses: true, shirt: 0x7a2e3a },
  { id: "sand", skin: 0xf0d0ac, hair: 0xc8a86a, hairStyle: "bun", shirt: 0xb89a6a },
  { id: "night", skin: 0x6f4530, hair: 0x14100c, hairStyle: "bald", glasses: true, shirt: 0x2a3244 },
  // Photo-face avatars: the photo wraps the front of the head; the animated
  // mouth bar sits over the lips so speech still shows.
  { id: "red", skin: 0xecc4a4, hair: 0x9a5636, hairStyle: "long", shirt: 0x2e3a52, photo: "./face-red.jpg" },
  { id: "gray", skin: 0xe4bc9c, hair: 0x8a8a84, hairStyle: "short", shirt: 0x38343c, photo: "./face-gray.jpg" },
  { id: "red2", skin: 0xecc4a4, hair: 0x9a5636, hairStyle: "long", shirt: 0x3e6b58, photo: "./face-red2.jpg", mouthY: 0.024 }
];

function mat(color, opts = {}) {
  return new THREE.MeshStandardMaterial({ color, metalness: 0, roughness: 0.85, ...opts });
}

function buildAvatar(v) {
  const skin = mat(v.skin);
  const hair = mat(v.hair, { roughness: 0.95 });
  const shirt = mat(v.shirt, { roughness: 0.9 });
  const dark = mat(0x2a1c18);
  const white = mat(0xf6f2ea, { roughness: 0.4 });

  const root = new THREE.Object3D();
  root.name = "AvatarRoot";
  const bone = (name, parent) => {
    const o = new THREE.Object3D();
    o.name = name;
    o.position.fromArray(BONE_T[name] || [0, 0, 0]);
    parent.add(o);
    return o;
  };
  const hips = bone("Hips", root);
  const spine = bone("Spine", hips);
  const neck = bone("Neck", spine);
  const head = bone("Head", neck);
  bone("LeftEye", head);
  bone("RightEye", head);
  const lHand = bone("LeftHand", spine);
  const rHand = bone("RightHand", spine);
  // Match upstream hand rest rotations so controller-driven poses look right.
  lHand.quaternion.set(0.5, 0.5, -0.5, 0.5);
  rHand.quaternion.set(0.5, -0.5, 0.5, 0.5);

  const add = (parent, name, geo, m, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0) => {
    const mesh = new THREE.Mesh(geo, m);
    mesh.name = name;
    mesh.position.set(x, y, z);
    mesh.rotation.set(rx, ry, rz);
    parent.add(mesh);
    return mesh;
  };

  // --- Torso (under Spine, hanging down toward hips) ---
  const torsoGeo = new THREE.CylinderGeometry(0.16, 0.13, 0.52, 10);
  torsoGeo.scale(1.35, 1, 0.75); // flatten front-to-back, widen shoulders
  add(spine, "Torso", torsoGeo, shirt, 0, -0.06, 0);
  add(spine, "ShoulderL", new THREE.SphereGeometry(0.075, 8, 6), shirt, 0.185, 0.16, 0);
  add(spine, "ShoulderR", new THREE.SphereGeometry(0.075, 8, 6), shirt, -0.185, 0.16, 0);
  add(spine, "Collar", new THREE.CylinderGeometry(0.055, 0.075, 0.1, 8), skin, 0, 0.24, 0);

  // --- Head (under Head bone; face is +z) ---
  const headGeo = new THREE.SphereGeometry(0.105, 14, 12);
  headGeo.scale(0.92, 1.08, 0.98);
  add(head, "Skull", headGeo, skin, 0, 0.075, 0.01);
  if (v.photo) {
    const faceMat = new THREE.MeshStandardMaterial({
      name: `Face_${v.id}`,
      color: 0xffffff,
      roughness: 0.85,
      metalness: 0
    });
    // Head-shaped face shell: front section of the skull ellipsoid with the
    // photo PLANAR-projected (not wrapped), plus subtle sculpted relief for
    // nose, brow and chin so the profile reads as a face.
    const faceGeo = new THREE.SphereGeometry(0.1065, 28, 22, Math.PI / 2 - 1.25, 2.5, 0.5, 2.15);
    faceGeo.scale(0.92, 1.08, 0.98);
    const pos = faceGeo.attributes.position;
    const nrm = faceGeo.attributes.normal;
    const gauss = (x, y, cx, cy, sx, sy) =>
      Math.exp(-(((x - cx) * (x - cx)) / (2 * sx * sx) + ((y - cy) * (y - cy)) / (2 * sy * sy)));
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
      if (z > 0.02) {
        const front = Math.min(1, (z - 0.02) / 0.07);
        const bump =
          0.011 * gauss(x, y, 0, -0.018, 0.013, 0.03) + // nose
          0.004 * gauss(x, y, 0, 0.028, 0.05, 0.012) +  // brow
          0.005 * gauss(x, y, 0, -0.085, 0.022, 0.016) + // chin
          0.003 * gauss(Math.abs(x), y, 0.05, -0.045, 0.02, 0.025); // cheeks
        pos.setXYZ(i, x + nrm.getX(i) * bump * front, y + nrm.getY(i) * bump * front, z + nrm.getZ(i) * bump * front);
      }
    }
    // Planar projection UVs from x/y (photo faces straight forward)
    const uvAttr = faceGeo.attributes.uv;
    const HX = 0.1065 * 0.92, HY = 0.1065 * 1.08;
    for (let i = 0; i < uvAttr.count; i++) {
      const x = pos.getX(i), y = pos.getY(i);
      uvAttr.setXY(i, x / (2 * HX * 0.98) + 0.5, 1 - (y / (2 * HY * 0.92) + 0.5));
    }
    faceGeo.computeVertexNormals();
    add(head, "FaceScreen", faceGeo, faceMat, 0, 0.072, 0.014);
  }
  if (!v.photo) add(head, "Nose", new THREE.SphereGeometry(0.016, 6, 5), skin, 0, 0.055, 0.115);
  add(head, "EarL", new THREE.SphereGeometry(0.024, 6, 5), skin, 0.095, 0.07, 0.005);
  add(head, "EarR", new THREE.SphereGeometry(0.024, 6, 5), skin, -0.095, 0.07, 0.005);
  // Eyes: whites + pupils, at the upstream eye positions (slightly pulled in)
  for (const s of v.photo ? [] : [1, -1]) {
    add(head, s > 0 ? "EyeL" : "EyeR", new THREE.SphereGeometry(0.02, 8, 6), white, s * 0.042, 0.085, 0.092);
    add(head, s > 0 ? "PupilL" : "PupilR", new THREE.SphereGeometry(0.009, 6, 5), dark, s * 0.042, 0.085, 0.108);
    add(head, s > 0 ? "BrowL" : "BrowR", new THREE.BoxGeometry(0.038, 0.008, 0.01), hair, s * 0.042, 0.115, 0.098);
  }

  // --- Mouth node: scale-audio-feedback target ---
  const mouth = new THREE.Object3D();
  mouth.name = "Mouth";
  mouth.position.set(0, v.photo ? (v.mouthY ?? 0.044) : 0.028, 0.1);
  head.add(mouth);
  add(mouth, "MouthMesh", new THREE.BoxGeometry(0.042, 0.011, 0.012), dark, 0, 0, v.photo ? 0.026 : 0);

  // --- Hair (slightly larger on photo avatars so it frames the face) ---
  const hairY = 0.075, capR = v.photo ? 0.121 : 0.112;
  if (v.hairStyle === "short") {
    const cap = new THREE.SphereGeometry(capR, 12, 8, 0, Math.PI * 2, 0, Math.PI * 0.55);
    add(head, "Hair", cap, hair, 0, hairY + 0.005, -0.005);
  } else if (v.hairStyle === "bun") {
    const cap = new THREE.SphereGeometry(capR, 12, 8, 0, Math.PI * 2, 0, Math.PI * 0.6);
    add(head, "Hair", cap, hair, 0, hairY, -0.005);
    add(head, "HairBun", new THREE.SphereGeometry(0.045, 8, 6), hair, 0, 0.16, -0.09);
  } else if (v.hairStyle === "long") {
    const cap = new THREE.SphereGeometry(capR, 12, 8, 0, Math.PI * 2, 0, Math.PI * 0.6);
    add(head, "Hair", cap, hair, 0, hairY, -0.005);
    const fall = new THREE.CylinderGeometry(0.1, 0.085, 0.24, 10, 1, true);
    add(head, "HairFall", fall, hair, 0, -0.02, -0.035);
  } else if (v.hairStyle === "bald") {
    // no hair cap; slight sheen strip
  } else if (v.hairStyle === "curly") {
    const cap = new THREE.SphereGeometry(capR + 0.012, 10, 7, 0, Math.PI * 2, 0, Math.PI * 0.58);
    add(head, "Hair", cap, hair, 0, hairY + 0.01, -0.005);
    add(head, "CurlL", new THREE.SphereGeometry(0.035, 6, 5), hair, 0.08, 0.14, 0.04);
    add(head, "CurlR", new THREE.SphereGeometry(0.035, 6, 5), hair, -0.08, 0.14, 0.04);
    add(head, "CurlT", new THREE.SphereGeometry(0.04, 6, 5), hair, 0, 0.17, -0.02);
  }

  // --- Beard ---
  if (v.beard) {
    const beardMat = mat(v.beard, { roughness: 0.95 });
    const jaw = new THREE.SphereGeometry(0.095, 10, 7, 0, Math.PI * 2, Math.PI * 0.55, Math.PI * 0.3);
    add(head, "Beard", jaw, beardMat, 0, 0.052, 0.028);
    add(head, "Moustache", new THREE.BoxGeometry(0.055, 0.012, 0.014), beardMat, 0, 0.042, 0.102);
  }

  // --- Glasses ---
  if (v.glasses) {
    const gMat = mat(0x1a1a1a, { roughness: 0.4 });
    for (const sx of [1, -1]) {
      const rim = new THREE.TorusGeometry(0.026, 0.004, 6, 12);
      add(head, sx > 0 ? "GlassL" : "GlassR", rim, gMat, sx * 0.042, 0.085, 0.104);
    }
    add(head, "GlassBridge", new THREE.BoxGeometry(0.03, 0.005, 0.006), gMat, 0, 0.088, 0.106);
    add(head, "GlassArmL", new THREE.BoxGeometry(0.004, 0.005, 0.09), gMat, 0.072, 0.085, 0.06);
    add(head, "GlassArmR", new THREE.BoxGeometry(0.004, 0.005, 0.09), gMat, -0.072, 0.085, 0.06);
  }

  // --- Hands: rounded mittens with a thumb hint, skin tone ---
  for (const [b, name, sx] of [[lHand, "HandL", 1], [rHand, "HandR", -1]]) {
    const palm = new THREE.SphereGeometry(0.045, 8, 6);
    palm.scale(1, 0.6, 1.5);
    add(b, name, palm, skin, 0, 0, 0);
    add(b, name + "_Thumb", new THREE.SphereGeometry(0.018, 6, 5), skin, sx * 0.04, 0.01, 0.03);
  }
  return root;
}

const feedbackFor = {}; // nodeName -> components, rebuilt per avatar
async function exportAvatar(v) {
  const scene = new THREE.Scene();
  scene.name = `Avatar_${v.id}`;
  scene.add(buildAvatar(v));

  const exporter = new GLTFExporter();
  const glb = await new Promise((res, rej) => exporter.parse(scene, res, rej, { binary: true }));
  const buf = Buffer.from(glb);
  const jsonLen = buf.readUInt32LE(12);
  const json = JSON.parse(buf.subarray(20, 20 + jsonLen).toString("utf8"));

  json.extensionsUsed = [...new Set([...(json.extensionsUsed || []), "MOZ_hubs_components"])];
  json.extensions = { ...(json.extensions || {}), MOZ_hubs_components: { version: 4 } };
  let tagged = 0;
  for (const node of json.nodes || []) {
    if (node.name === "Mouth") {
      node.extensions = {
        MOZ_hubs_components: { "scale-audio-feedback": { minScale: 1, maxScale: 2.4 } }
      };
      tagged++;
    }
  }
  if (tagged !== 1) throw new Error(`Mouth node tagging failed for ${v.id}`);

  let binChunk = buf.subarray(20 + jsonLen);
  if (v.photo) {
    const { readFileSync } = await import("fs");
    const img = readFileSync(new URL(v.photo, import.meta.url));
    let binData = Buffer.from(binChunk.subarray(8, 8 + binChunk.readUInt32LE(0)));
    const pad = (4 - (binData.length % 4)) % 4;
    const offset = binData.length + pad;
    binData = Buffer.concat([binData, Buffer.alloc(pad), img]);
    const endPad = (4 - (binData.length % 4)) % 4;
    binData = Buffer.concat([binData, Buffer.alloc(endPad)]);
    json.bufferViews = json.bufferViews || [];
    json.bufferViews.push({ buffer: 0, byteOffset: offset, byteLength: img.length });
    json.images = json.images || [];
    json.images.push({ bufferView: json.bufferViews.length - 1, mimeType: "image/jpeg" });
    json.samplers = json.samplers || [];
    json.samplers.push({ magFilter: 9729, minFilter: 9987, wrapS: 33071, wrapT: 33071 });
    json.textures = json.textures || [];
    json.textures.push({ sampler: json.samplers.length - 1, source: json.images.length - 1 });
    const m = (json.materials || []).find(mm => mm.name === `Face_${v.id}`);
    if (!m) throw new Error(`Face material missing for ${v.id}`);
    m.pbrMetallicRoughness = {
      ...(m.pbrMetallicRoughness || {}),
      baseColorTexture: { index: json.textures.length - 1 },
      baseColorFactor: [1, 1, 1, 1]
    };
    const newBinHeader = Buffer.alloc(8);
    newBinHeader.writeUInt32LE(binData.length, 0);
    newBinHeader.writeUInt32LE(0x004e4942, 4);
    binChunk = Buffer.concat([newBinHeader, binData]);
    json.buffers[0].byteLength = binData.length;
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
  const file = join(outdir, `avatar-${v.id}.glb`);
  writeFileSync(file, Buffer.concat([header, jsonHeader, jsonOut, binChunk]));
  console.log(`${file}: ${12 + 8 + jsonOut.length + binChunk.length} bytes, ${json.nodes.length} nodes`);
}

for (const v of VARIANTS) await exportAvatar(v);
console.log("done");
