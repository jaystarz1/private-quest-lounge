# Renders bedroom/hot-tub vantage shots with red spheres at Seat_* + 0.45
# (where the client draws the waypoint icon) to check markers sit on furniture.
# Usage: blender -b --factory-startup -P render-seat-markers.py -- <model.glb> <outdir>
import bpy, sys, math, os
from mathutils import Euler

argv = sys.argv[sys.argv.index("--") + 1:]
src, outdir = argv
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene

mat = bpy.data.materials.new("Marker")
mat.use_nodes = True
b = mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (1, 0.05, 0.05, 1)
b.inputs["Emission Color"].default_value = (1, 0.1, 0.1, 1)
b.inputs["Emission Strength"].default_value = 4.0

for o in list(sc.collection.all_objects):
    if o.name.startswith("Seat_"):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(o.location.x, o.location.y, o.location.z + 0.45))
        s = bpy.context.active_object
        s.name = f"MK_{o.name}"
        s.data.materials.append(mat)

sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(55), 0, math.radians(30))
sc.collection.objects.link(sun)
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1152, 648
sc.render.image_settings.file_format = 'JPEG'
sc.render.image_settings.quality = 85
sc.view_settings.view_transform = 'Standard'
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

def look(name, x, y, z, toward, pitch=0):
    tx, ty = toward
    yaw = math.degrees(math.atan2(-(tx - x), ty - y))
    shot(name, x, y, z, yaw, pitch)

look("nw-bedroom", -6.80, 5.10, 4.90, (-9.20, 7.20), pitch=-5)
look("ne-bedroom", 7.15, 4.90, 4.90, (8.90, 7.00), pitch=-5)
look("ne-bedroom-toward-bed", 7.15, 7.30, 4.90, (9.00, 5.60), pitch=-8)
look("sw-bedroom", -7.20, -2.20, 4.90, (-9.00, -3.90), pitch=-5)
look("hot-tub-deck", -7.85, -8.65, 1.55, (-9.75, -7.15), pitch=-10)
look("sky-den", 1.50, -7.50, 4.90, (1.50, -9.25), pitch=-5)
