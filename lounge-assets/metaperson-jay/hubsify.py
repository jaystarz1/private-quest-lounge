# Converts the MetaPerson full-body export into a lounge half-body avatar:
# - deletes all geometry weighted to leg bones and the leg bones themselves
# - keeps the arm chains so the tracked hands stay attached to the torso
# - deletes finger bones (Hubs doesn't drive them; weights collapse to the hand)
# - adds a Mouth empty under Head for scale-audio-feedback tagging
# - exports GLB alongside the input
# Run: blender -b -P hubsify.py -- <in.glb> <out.glb>
import bpy, json, struct, sys

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv[0], argv[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)

LEG_PREFIXES = ("LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToe",
                "RightUpLeg", "RightLeg", "RightFoot", "RightToe")
FINGER_PREFIXES = ("LeftHandThumb", "LeftHandIndex", "LeftHandMiddle", "LeftHandRing", "LeftHandPinky",
                   "RightHandThumb", "RightHandIndex", "RightHandMiddle", "RightHandRing", "RightHandPinky")

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")

# --- delete leg-weighted vertices from every mesh ---
leg_groups = lambda o: [g.index for g in o.vertex_groups if g.name.startswith(LEG_PREFIXES)]
for obj in [o for o in bpy.data.objects if o.type == "MESH"]:
    idxs = set(leg_groups(obj))
    if not idxs:
        continue
    doomed = []
    for v in obj.data.vertices:
        w = {g.group: g.weight for g in v.groups}
        tot = sum(w.values()) or 1.0
        legw = sum(wt for gi, wt in w.items() if gi in idxs)
        if legw / tot > 0.5 or (obj.matrix_world @ v.co).z < 0.95:
            doomed.append(v.index)
    if doomed:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")
        for i in doomed:
            obj.data.vertices[i].select = True
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.delete(type="VERT")
        bpy.ops.object.mode_set(mode="OBJECT")
        print(f"{obj.name}: removed {len(doomed)} leg verts")

# --- merge finger weights into the parent hand, then drop finger bones ---
for obj in [o for o in bpy.data.objects if o.type == "MESH"]:
    for side in ("Left", "Right"):
        hand = obj.vertex_groups.get(side + "Hand")
        if not hand:
            continue
        for vg in [g for g in obj.vertex_groups if g.name.startswith(tuple(p for p in FINGER_PREFIXES if p.startswith(side)))]:
            for v in obj.data.vertices:
                for g in v.groups:
                    if g.group == vg.index and g.weight > 0:
                        hand.add([v.index], g.weight, "ADD")
            obj.vertex_groups.remove(vg)

# --- fold the extra spine/neck bones into the 4-bone chain Hubs IK expects ---
# Hubs ik-controller computes hips-to-head as Spine.t + Neck.t + Head.t and
# assumes Hips is at the model origin. MetaPerson's Spine1/Spine2/Neck1/Neck2
# plus the 0.95 m Hips offset made avatars float ~1.2 m above the player.
FOLD = (("Spine1", "Spine"), ("Spine2", "Spine"), ("Neck1", "Neck"), ("Neck2", "Neck"))
for obj in [o for o in bpy.data.objects if o.type == "MESH"]:
    for bone_name, target_name in FOLD:
        vg = obj.vertex_groups.get(bone_name)
        if not vg:
            continue
        target = obj.vertex_groups.get(target_name) or obj.vertex_groups.new(name=target_name)
        for v in obj.data.vertices:
            for g in v.groups:
                if g.group == vg.index and g.weight > 0:
                    target.add([v.index], g.weight, "ADD")
        obj.vertex_groups.remove(vg)

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
for eb in list(arm.data.edit_bones):
    if eb.name.startswith(LEG_PREFIXES) or eb.name.startswith(FINGER_PREFIXES):
        arm.data.edit_bones.remove(eb)
for bone_name, target_name in FOLD:
    eb = arm.data.edit_bones.get(bone_name)
    if not eb:
        continue
    target = arm.data.edit_bones[target_name]
    for child in list(eb.children):
        child.use_connect = False
        child.parent = target
    arm.data.edit_bones.remove(eb)

# Hubs' ik-controller writes chest-relative transforms directly to the named
# hand end effectors. Keep the modeled arm chain for its geometry, but make the
# hand bones direct children of Spine so tracked hand positions stay correct.
spine = arm.data.edit_bones["Spine"]
for side in ("Left", "Right"):
    hand = arm.data.edit_bones.get(side + "Hand")
    if not hand:
        continue
    rest_matrix = hand.matrix.copy()
    hand.parent = spine
    hand.use_connect = False
    hand.matrix = rest_matrix
# Shift the whole rig so the Hips head lands at the armature origin (edit-bone
# coords are absolute, so child world placement is preserved).
hips_off = arm.data.edit_bones["Hips"].head.copy()
for eb in arm.data.edit_bones:
    eb.head -= hips_off
    eb.tail -= hips_off
bpy.ops.object.mode_set(mode="OBJECT")

# Shift mesh geometry down by the same amount so skinning stays aligned.
# CRITICAL: meshes with shape keys (the face) ignore raw vertex edits — the
# shape-key point data is what exports. Shift every key block as well, or the
# head renders 0.95 m above its bone while the body sits correctly.
off_world = arm.matrix_world @ hips_off - arm.matrix_world.translation
for obj in [o for o in bpy.data.objects if o.type == "MESH"]:
    inv = obj.matrix_world.inverted()
    local_off = inv.to_3x3() @ off_world
    if obj.data.shape_keys:
        for kb in obj.data.shape_keys.key_blocks:
            for pt in kb.data:
                pt.co -= local_off
    for v in obj.data.vertices:
        v.co -= local_off

# --- Mouth empty under Head bone, at the lips ---
head = arm.pose.bones.get("Head")
mouth = bpy.data.objects.new("Mouth", None)
bpy.context.scene.collection.objects.link(mouth)
mouth.parent = arm
mouth.parent_type = "BONE"
mouth.parent_bone = "Head"
# bone-parent origin is the TAIL of Head; nudge forward/down toward lips
mouth.location = (0, 0.04, -0.06)

# Personal avatars are rendered close to the camera, but fifteen 1024-square
# maps per avatar cost far more Quest GPU memory than their compressed GLBs
# suggest. A 512 cap preserves face detail while cutting decoded texture memory
# by roughly three quarters.
for image in bpy.data.images:
    width, height = image.size
    if width <= 512 and height <= 512:
        continue
    ratio = min(512 / width, 512 / height)
    image.scale(max(1, round(width * ratio)), max(1, round(height * ratio)))

bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", export_yup=True)

# Blender does not preserve Hubs component extensions. Tag every exported mesh
# carrying MetaPerson's jawOpen target so voice volume drives the face and lower
# teeth. Keeping this inside the exporter prevents a later avatar rollback from
# silently replacing a working tagged GLB with an untagged one.
with open(dst, "rb") as handle:
    raw = handle.read()
json_len = struct.unpack_from("<I", raw, 12)[0]
gltf = json.loads(raw[20:20 + json_len].decode("utf-8"))
tagged = 0
for node in gltf["nodes"]:
    if "mesh" not in node:
        continue
    names = gltf["meshes"][node["mesh"]].get("extras", {}).get("targetNames", [])
    if "jawOpen" not in names:
        continue
    components = node.setdefault("extensions", {}).setdefault("MOZ_hubs_components", {})
    components["morph-audio-feedback"] = {"name": "jawOpen", "minValue": 0, "maxValue": 1.2}
    tagged += 1
if not tagged:
    raise RuntimeError("exported avatar has no jawOpen morph targets")
gltf.setdefault("extensions", {}).setdefault("MOZ_hubs_components", {})["version"] = 4
gltf["extensionsUsed"] = list(dict.fromkeys(gltf.get("extensionsUsed", []) + ["MOZ_hubs_components"]))
json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)
rest = raw[20 + json_len:]
header = struct.pack("<4sIIII", b"glTF", 2, 20 + len(json_bytes) + len(rest), len(json_bytes), 0x4E4F534A)
with open(dst, "wb") as handle:
    handle.write(header + json_bytes + rest)
print(f"exported {dst} with morph-audio-feedback on {tagged} jawOpen meshes")
