# Decorator walkthrough: loads the styled penthouse GLB, dumps a material->
# world-bbox map (French names locate furniture: lit=bed, chaise/fauteuil=chair,
# tabouret=stool, canape=sofa, vitre/verre/fenetre=glass, plante=plant), then
# renders viewpoint images around both floors.
# Usage: blender -b --factory-startup -P inspect-walkthrough.py -- <in.glb> <outdir>
import bpy, sys, os, math, json
from mathutils import Vector, Euler

src, outdir = sys.argv[-2], sys.argv[-1]
os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene

# --- Material -> world bbox of faces using it --------------------------------
KEYS = ("lit", "chaise", "fauteuil", "tabouret", "canape", "vitre", "verre",
        "fenetre", "plante", "rideau", "matelas", "oreiller", "couette",
        "coussin", "lampe", "miroir", "tapis", "moquette", "table", "bureau",
        "etagere", "armoire", "commode", "tele", "baignoire", "lavabo", "wc",
        "douche")
boxes = {}
for ob in [o for o in sc.collection.all_objects if o.type == 'MESH']:
    mw = ob.matrix_world
    mats = [m.name if m else '?' for m in ob.data.materials] or ['?']
    for p in ob.data.polygons:
        mn = mats[min(p.material_index, len(mats) - 1)]
        c = mw @ p.center
        b = boxes.setdefault(mn, [1e9, 1e9, 1e9, -1e9, -1e9, -1e9, 0])
        b[0] = min(b[0], c.x); b[1] = min(b[1], c.y); b[2] = min(b[2], c.z)
        b[3] = max(b[3], c.x); b[4] = max(b[4], c.y); b[5] = max(b[5], c.z)
        b[6] += 1

report = {}
for mn, b in sorted(boxes.items()):
    low = mn.lower()
    tags = [k for k in KEYS if k in low]
    report[mn] = {"bbox": [round(v, 2) for v in b[:6]], "faces": b[6], "tags": tags}
with open(os.path.join(outdir, "materials.json"), "w") as f:
    json.dump(report, f, indent=1)
for mn, r in report.items():
    if r["tags"]:
        print("TAGGED", ",".join(r["tags"]), mn, r["bbox"], r["faces"])

# --- Objects (empties + meshes) with locations -------------------------------
with open(os.path.join(outdir, "objects.txt"), "w") as f:
    for ob in sc.collection.all_objects:
        loc = ob.matrix_world.translation
        f.write(f"{ob.type} {ob.name} ({loc.x:.2f},{loc.y:.2f},{loc.z:.2f})\n")

# --- Render walkthrough ------------------------------------------------------
sc.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types, 'SceneEEVEE') and 'NEXT' in dir(bpy.types) else 'BLENDER_EEVEE'
try:
    sc.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception:
    sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1152, 648
sc.render.image_settings.file_format = 'JPEG'
sc.render.image_settings.quality = 85
w = bpy.data.worlds.new("W"); sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.55, 0.6, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8

cam = bpy.data.cameras.new("C"); cam.lens = 16
co = bpy.data.objects.new("Cam", cam)
sc.collection.objects.link(co)
sc.camera = co

def shot(name, x, y, z, yaw_deg, pitch_deg=0):
    co.location = (x, y, z)
    co.rotation_euler = Euler((math.radians(90 + pitch_deg), 0, math.radians(yaw_deg)), 'XYZ')
    sc.render.filepath = os.path.join(outdir, name + ".jpg")
    bpy.ops.render.render(write_still=True)
    print("SHOT", name)

# yaw 0 looks -Y? Blender camera looks down -Z; with rx=90 it looks along +Y when yaw=180.
# Convention here: yaw measured so 0 => looking +Y (north), 90 => looking -X (west), 180 => -Y, 270 => +X.
def look(name, x, y, z, toward, pitch=0):
    tx, ty = toward
    yaw = math.degrees(math.atan2(-(tx - x), ty - y))
    shot(name, x, y, z, yaw, pitch)

look("01-lounge-from-hall", -2.0, 2.0, 1.6, (-9, 7))
look("02-lounge-sofa-tv", -6.5, 8.0, 1.6, (-11, 5))
look("03-piano-corner", -5.5, 2.0, 1.6, (-9, -1.5))
look("04-south-rooms", -4.0, -3.0, 1.6, (-6, -9))
look("05-front-door", 1.5, -4.0, 1.6, (-1, -8))
look("06-dining-east", 4.0, 2.0, 1.6, (10, 6))
look("07-bar", 6.5, 2.0, 1.5, (10, -0.5))
look("08-kitchen", 2.0, 6.5, 1.6, (6, 9))
look("09-patio", -1.0, 6.0, 1.7, (2.5, 9.5))
look("10-north-view-glass", 0.0, 2.0, 1.7, (0, 10))
look("11-stairs-up", 1.5, -1.5, 1.6, (1.5, 1.5), pitch=15)
look("12-upper-landing", 1.5, 0.0, 4.9, (-4, 0))
look("13-upper-west", -3.0, 0.0, 4.9, (-9, 4))
look("14-upper-east", 3.5, 0.0, 4.9, (9, 3))
look("15-upper-north", 0.0, 3.0, 4.9, (5, 8))
look("16-upper-south", 0.0, -3.0, 4.9, (-5, -8))
look("19-lobby-gallery", -4.1, -9.05, 1.65, (-4.55, -6.57))
look("20-patio-glass-clean", 0.0, 2.0, 1.7, (2.8, 4.05))
look("21-piano-keys", -6.30, -1.30, 1.25, (-7.65, -1.30), pitch=-20)
look("22-hot-tub-deck", -7.85, -8.65, 1.55, (-9.75, -7.15), pitch=-10)
look("23-nw-bedroom", -6.80, 5.10, 4.90, (-9.20, 7.20), pitch=-5)
look("24-ne-bedroom", 7.15, 4.90, 4.90, (8.90, 7.00), pitch=-5)
look("25-sw-bedroom", -7.20, -2.20, 4.90, (-9.00, -3.90), pitch=-5)
look("26-gym", -0.20, -4.10, 4.90, (-2.00, -5.20), pitch=-5)
look("27-east-suite", 7.90, -1.10, 4.90, (9.00, -3.00), pitch=-5)
look("28-sky-den", 1.50, -7.50, 4.90, (1.50, -9.25), pitch=-5)
look("17-birdseye-down", 0.0, 0.0, 2.6, (0.01, 0.01), pitch=-88)
look("18-birdseye-up", 0.0, 0.0, 6.4, (0.01, 0.01), pitch=-88)
print("DONE")
