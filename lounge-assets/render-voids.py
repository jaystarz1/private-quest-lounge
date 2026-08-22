# Plan cutaways + eye-height renders at the void slabs.
# Usage: blender -b --factory-startup -P render-voids.py -- <final.glb> <outdir>
import bpy, sys, os, math
from mathutils import Euler
src, outdir = sys.argv[-2], sys.argv[-1]
os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1152, 648
sc.render.image_settings.file_format = 'JPEG'
sc.render.image_settings.quality = 85
w = bpy.data.worlds.new("W"); sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.55, 0.6, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8
nav = bpy.data.objects.get('NavMesh')
if nav:
    nav.hide_render = True
cam = bpy.data.cameras.new("C"); cam.lens = 16
co = bpy.data.objects.new("Cam", cam)
sc.collection.objects.link(co)
sc.camera = co

def shot(name):
    sc.render.filepath = os.path.join(outdir, name + ".jpg")
    bpy.ops.render.render(write_still=True)
    print("SHOT", name)

# --- top-down plans, roof clipped ---
cam.type = 'ORTHO'
cam.ortho_scale = 27
co.rotation_euler = Euler((0, 0, 0), 'XYZ')
co.location = (0, 0, 30)
cam.clip_start = 30 - 2.4   # cut at z=2.4 -> ground floor
cam.clip_end = 100
shot("plan-ground")
cam.clip_start = 30 - 6.2   # cut at z=6.2 -> upper floor
shot("plan-upper")

# --- eye-height perspective shots ---
cam.type = 'PERSP'
cam.clip_start = 0.1
def look(name, x, y, z, toward, pitch=0):
    tx, ty = toward
    yaw = math.degrees(math.atan2(-(tx - x), ty - y))
    co.location = (x, y, z)
    co.rotation_euler = Euler((math.radians(90 + pitch), 0, math.radians(yaw)), 'XYZ')
    shot(name)

# SW slab
look("sw-slab-north", -9.8, -7.6, 1.5, (-9.8, -4.0))
look("sw-slab-south", -9.8, -6.5, 1.5, (-9.8, -9.8))
look("sw-slab-east", -10.5, -7.5, 1.5, (-6.0, -7.5))
# SE slab
look("se-slab-north", 9.8, -7.6, 1.5, (9.8, -4.0))
look("se-slab-west", 10.5, -7.5, 1.5, (6.0, -7.5))
look("se-slab-south", 9.8, -6.0, 1.5, (9.8, -9.8))
# front-door hall, looking south + standing at the south row
look("frontdoor-south", -0.95, -6.2, 1.5, (-0.95, -9.8))
look("frontdoor-out", -3.0, -9.0, 1.5, (-6.0, -9.0))
look("hall-return", -0.95, -8.8, 1.5, (-0.95, -4.0))
# upper black strip
look("up-strip-north", 4.3, -8.8, 4.9, (4.3, -5.0))
look("up-strip-south", 4.3, -7.8, 4.9, (4.3, -9.8))
look("up-strip-east", 3.6, -8.6, 4.9, (7.5, -8.6))
look("up-southrooms", 5.2, -6.8, 4.9, (3.0, -9.5))
print("VDONE")
