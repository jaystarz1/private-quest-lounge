#!/usr/bin/env node

// Losslessly repacks a GLB while resizing embedded JPEG/PNG textures. Geometry,
// accessors, materials, morph targets and custom Hubs extensions are copied
// without interpretation, which makes this safer for the lounge assets than a
// general-purpose model optimizer.
//
// Usage:
//   node resize-glb-textures.mjs --max-size 1024 [--quality 88] input.glb output.glb

import { spawnSync } from "child_process";
import { readFileSync, writeFileSync } from "fs";
import { basename } from "path";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  return index === -1 ? fallback : args[index + 1];
};
const positional = args.filter((value, index) => !value.startsWith("--") && !args[index - 1]?.startsWith("--"));
const maxSize = Number(option("--max-size", 1024));
const quality = Number(option("--quality", 88));
const [inputFile, outputFile] = positional;

if (!inputFile || !outputFile || !Number.isInteger(maxSize) || maxSize < 64 || maxSize > 4096) {
  throw new Error("usage: resize-glb-textures.mjs --max-size 1024 [--quality 88] input.glb output.glb");
}
if (!Number.isInteger(quality) || quality < 1 || quality > 100) throw new Error("quality must be 1..100");

const raw = readFileSync(inputFile);
if (raw.readUInt32LE(0) !== 0x46546c67 || raw.readUInt32LE(4) !== 2) throw new Error("input is not a GLB v2 file");

let offset = 12;
let json;
let binary;
while (offset + 8 <= raw.length) {
  const length = raw.readUInt32LE(offset);
  const type = raw.readUInt32LE(offset + 4);
  const chunk = raw.subarray(offset + 8, offset + 8 + length);
  if (type === 0x4e4f534a) json = JSON.parse(chunk.toString("utf8").replace(/[\0 ]+$/, ""));
  if (type === 0x004e4942) binary = chunk;
  offset += 8 + length;
}
if (!json || !binary || json.buffers?.length !== 1) throw new Error("expected one embedded GLB buffer");

const imageDimensions = data => {
  if (data[0] === 0x89 && data.toString("ascii", 1, 4) === "PNG") {
    return [data.readUInt32BE(16), data.readUInt32BE(20)];
  }
  if (data[0] === 0xff && data[1] === 0xd8) {
    for (let cursor = 2; cursor + 9 < data.length; ) {
      if (data[cursor] !== 0xff) {
        cursor++;
        continue;
      }
      const marker = data[cursor + 1];
      const length = data.readUInt16BE(cursor + 2);
      const isStartOfFrame =
        (marker >= 0xc0 && marker <= 0xc3) ||
        (marker >= 0xc5 && marker <= 0xc7) ||
        (marker >= 0xc9 && marker <= 0xcb) ||
        (marker >= 0xcd && marker <= 0xcf);
      if (isStartOfFrame) return [data.readUInt16BE(cursor + 7), data.readUInt16BE(cursor + 5)];
      cursor += 2 + length;
    }
  }
  return null;
};

const replacements = new Map();
let originalPixels = 0;
let resizedPixels = 0;
let resizedCount = 0;

for (const [index, image] of (json.images || []).entries()) {
  if (image.bufferView === undefined || !["image/jpeg", "image/png"].includes(image.mimeType)) continue;
  const view = json.bufferViews[image.bufferView];
  if ((view.buffer || 0) !== 0) throw new Error(`image ${index} references an external buffer`);
  const start = view.byteOffset || 0;
  const source = binary.subarray(start, start + view.byteLength);
  const dimensions = imageDimensions(source);
  if (!dimensions) throw new Error(`cannot read dimensions for image ${index}`);
  const [width, height] = dimensions;
  originalPixels += width * height;
  if (width <= maxSize && height <= maxSize) {
    resizedPixels += width * height;
    continue;
  }

  const format = image.mimeType === "image/png" ? "png" : "jpeg";
  const magickArgs = [`${format}:-`, "-resize", `${maxSize}x${maxSize}>`, "-strip"];
  if (format === "jpeg") magickArgs.push("-quality", String(quality));
  magickArgs.push(`${format}:-`);
  const result = spawnSync("magick", magickArgs, { input: source, maxBuffer: 64 * 1024 * 1024 });
  if (result.status !== 0) throw new Error(`ImageMagick failed for image ${index}: ${result.stderr}`);
  const resized = Buffer.from(result.stdout);
  const nextDimensions = imageDimensions(resized);
  if (!nextDimensions) throw new Error(`cannot validate resized image ${index}`);
  replacements.set(image.bufferView, resized);
  resizedPixels += nextDimensions[0] * nextDimensions[1];
  resizedCount++;
  console.log(
    `${basename(inputFile)} image ${index} ${image.name || ""}: ${width}x${height} -> ${nextDimensions[0]}x${nextDimensions[1]}`
  );
}

const pieces = [];
let binaryLength = 0;
for (const [index, view] of json.bufferViews.entries()) {
  if ((view.buffer || 0) !== 0) throw new Error(`bufferView ${index} references an external buffer`);
  const padding = (4 - (binaryLength % 4)) % 4;
  if (padding) {
    pieces.push(Buffer.alloc(padding));
    binaryLength += padding;
  }
  const start = view.byteOffset || 0;
  const contents = replacements.get(index) || binary.subarray(start, start + view.byteLength);
  view.byteOffset = binaryLength;
  view.byteLength = contents.length;
  pieces.push(contents);
  binaryLength += contents.length;
}

json.buffers[0].byteLength = binaryLength;
let binaryOut = Buffer.concat(pieces);
const binaryPadding = (4 - (binaryOut.length % 4)) % 4;
if (binaryPadding) binaryOut = Buffer.concat([binaryOut, Buffer.alloc(binaryPadding)]);

let jsonOut = Buffer.from(JSON.stringify(json), "utf8");
const jsonPadding = (4 - (jsonOut.length % 4)) % 4;
if (jsonPadding) jsonOut = Buffer.concat([jsonOut, Buffer.alloc(jsonPadding, 0x20)]);

const header = Buffer.alloc(12);
header.write("glTF", 0);
header.writeUInt32LE(2, 4);
header.writeUInt32LE(12 + 8 + jsonOut.length + 8 + binaryOut.length, 8);
const jsonHeader = Buffer.alloc(8);
jsonHeader.writeUInt32LE(jsonOut.length, 0);
jsonHeader.writeUInt32LE(0x4e4f534a, 4);
const binaryHeader = Buffer.alloc(8);
binaryHeader.writeUInt32LE(binaryOut.length, 0);
binaryHeader.writeUInt32LE(0x004e4942, 4);

writeFileSync(outputFile, Buffer.concat([header, jsonHeader, jsonOut, binaryHeader, binaryOut]));
console.log(
  `Wrote ${outputFile}: ${resizedCount} textures resized; decoded base RGBA ${(originalPixels * 4 / 1048576).toFixed(1)} MiB -> ${(resizedPixels * 4 / 1048576).toFixed(1)} MiB`
);
