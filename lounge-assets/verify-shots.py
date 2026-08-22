import bpy, sys, os, math
from mathutils import Euler
src, outdir = sys.argv[-2], sys.argv[-1]
os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
nav = bpy.data.objects.get('NavMesh')
if nav:
    nav.hide_render = True
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
def look(name, x, y, z, toward, pitch=0):
    tx, ty = toward
    yaw = math.degrees(math.atan2(-(tx - x), ty - y))
    co.location = (x, y, z)
    co.rotation_euler = Euler((math.radians(90 + pitch), 0, math.radians(yaw)), 'XYZ')
    sc.render.filepath = os.path.join(outdir, name + ".jpg")
    bpy.ops.render.render(write_still=True)
    print("SHOT", name)
look("v1-piano", -5.5, 2.0, 1.6, (-9, -1.5))
look("v2-lounge", -6.5, 8.0, 1.6, (-11, 5))
look("v3-bar-eastglass", 6.5, 2.0, 1.5, (10, -0.5))
look("v4-dining", 4.0, 2.0, 1.6, (10, 6))
look("v5-bed-NW", -6.8, 5.8, 4.9, (-9.6, 7.4))
look("v6-bed-NE", 7.6, 8.9, 4.9, (9.6, 6.2))
look("v7-bed-SW", -6.6, -2.0, 4.9, (-9.4, -3.9))
look("v8-patio", -1.0, 6.0, 1.7, (2.5, 9.5))
look("v9-fireplace", -8.0, 4.2, 1.2, (-10.7, 4.0))
look("v10-terrace-dining", 1.2, 6.6, 1.7, (4.6, 6.8))
look("v11-hall-plant", -0.5, 1.5, 1.5, (-1.1, -0.6))
look("v12-westglass", -7.0, 1.0, 1.6, (-11.2, 2.0))
look("v13-lobby", -6.9, -7.0, 1.5, (-2.8, -9.2))
look("v14-lobby-lifts", -4.1, -7.0, 1.5, (-4.7, -9.7))
look("v15-sw-terrace", -8.1, -5.3, 1.6, (-10.9, -8.6))
look("v16-se-terrace", 10.9, -5.1, 1.6, (8.5, -8.7))
look("v17-walk", 5.2, -8.9, 1.5, (9.5, -7.6))
look("v18-den", 0.0, -7.6, 4.7, (2.2, -9.3))
look("v19-den-west", 2.6, -8.4, 4.7, (-2.5, -8.5))
look("v20-eastview", 6.5, 2.0, 1.6, (11.5, 2.0))
look("v21-westview", -9.5, -7.0, 1.6, (-13.0, -7.0))
print("VDONE")
