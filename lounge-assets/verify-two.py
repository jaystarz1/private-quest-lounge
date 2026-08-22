import bpy, sys, os, math
from mathutils import Euler
src, outdir = sys.argv[-2], sys.argv[-1]
os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
nav = bpy.data.objects.get('NavMesh')
if nav: nav.hide_render = True
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
sc.collection.objects.link(co); sc.camera = co
def look(name, x, y, z, toward, pitch=0):
    tx, ty = toward
    yaw = math.degrees(math.atan2(-(tx - x), ty - y))
    co.location = (x, y, z)
    co.rotation_euler = Euler((math.radians(90 + pitch), 0, math.radians(yaw)), 'XYZ')
    sc.render.filepath = os.path.join(outdir, name + ".jpg")
    bpy.ops.render.render(write_still=True)
    print("SHOT", name)
look("se-mass", 10.9, -5.1, 1.6, (8.5, -8.7))
look("walkup", 5.2, -8.9, 1.5, (3.0, -6.5), pitch=-18)
