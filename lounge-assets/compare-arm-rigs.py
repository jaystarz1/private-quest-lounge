#!/usr/bin/env python3
"""Compare the arm bind geometry of two GLB avatars."""

import argparse
import json
import struct

import numpy as np


BONES = (
    "Spine",
    "LeftShoulder",
    "LeftArm",
    "LeftForeArm",
    "LeftForeArm1",
    "LeftForeArm2",
    "LeftHand",
    "RightShoulder",
    "RightArm",
    "RightForeArm",
    "RightForeArm1",
    "RightForeArm2",
    "RightHand",
)


def read_glb(path):
    with open(path, "rb") as source:
        magic, version, length = struct.unpack("<III", source.read(12))
        if magic != 0x46546C67 or version != 2:
            raise ValueError(f"{path}: not a glTF 2 GLB")
        while source.tell() < length:
            chunk_length, chunk_type = struct.unpack("<II", source.read(8))
            chunk = source.read(chunk_length)
            if chunk_type == 0x4E4F534A:
                return json.loads(chunk.rstrip(b" \t\r\n\0"))
    raise ValueError(f"{path}: missing JSON chunk")


def node_matrix(node):
    if "matrix" in node:
        return np.array(node["matrix"], dtype=float).reshape((4, 4), order="F")
    translation = np.array(node.get("translation", [0, 0, 0]), dtype=float)
    scale = np.array(node.get("scale", [1, 1, 1]), dtype=float)
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    rotation = np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0],
            [0, 0, 0, 1],
        ],
        dtype=float,
    )
    rotation[:3, :3] *= scale
    rotation[:3, 3] = translation
    return rotation


def bind_geometry(path):
    gltf = read_glb(path)
    nodes = gltf["nodes"]
    parents = {}
    for parent_index, node in enumerate(nodes):
        for child_index in node.get("children", []):
            parents[child_index] = parent_index

    world_cache = {}

    def world(index):
        if index not in world_cache:
            local = node_matrix(nodes[index])
            world_cache[index] = world(parents[index]) @ local if index in parents else local
        return world_cache[index]

    indices = {node.get("name"): index for index, node in enumerate(nodes)}
    missing = [name for name in BONES if name not in indices]
    if missing:
        raise ValueError(f"{path}: missing {', '.join(missing)}")
    spine_inverse = np.linalg.inv(world(indices["Spine"]))
    points = {}
    for name in BONES:
        points[name] = (spine_inverse @ world(indices[name]) @ np.array([0, 0, 0, 1]))[:3]
    return points


def normalized(vector):
    return vector / np.linalg.norm(vector)


def print_geometry(label, points):
    print(label)
    for side in ("Left", "Right"):
        shoulder = points[f"{side}Shoulder"]
        arm = points[f"{side}Arm"]
        elbow = points[f"{side}ForeArm"]
        hand = points[f"{side}Hand"]
        print(
            f"  {side}: shoulder={shoulder.round(6)} arm={arm.round(6)} "
            f"elbow={elbow.round(6)} hand={hand.round(6)}"
        )
        print(
            f"        shoulder-axis={normalized(arm - shoulder).round(6)} "
            f"upper-axis={normalized(elbow - arm).round(6)} "
            f"bind-elbow-plane={normalized(np.cross(elbow - shoulder, hand - shoulder)).round(6)}"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("glbs", nargs="+")
    args = parser.parse_args()
    for path in args.glbs:
        print_geometry(path, bind_geometry(path))


if __name__ == "__main__":
    main()
