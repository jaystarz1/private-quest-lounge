# Floor-plan renders (ceiling clipped via camera clip_start) + horizontal fan
# ray probes that name the object/material first hit — used to identify window
# panes, dark panels, plants, and bedding by name.
# Usage: blender -b --factory-startup -P probe-plans.py -- <in.glb> <outdir>
import bpy, sys, os, math
from mathutils import Vector, Euler

src, outdir = sys.argv[-2], sys.argv[-1]
os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()

def matname(ob, fi):
    try:
        me = ob.data
        mi = me.polygons[fi].material_index
        return me.materials[mi].name if me.materials and me.materials[mi] else "?"
    except Exception:
        return "?"

def fan(label, x, y, z, a0=0, a1=360, step=10, dist=14):
    print(f"=== FAN {label} from ({x},{y},{z}) ===")
    for adeg in range(a0, a1, step):
        a = math.radians(adeg)
        d = Vector((math.cos(a), math.sin(a), 0))
        ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, Vector((x, y, z)), d, distance=dist)
        if ok:
            print(f"  {adeg:3d}deg d={ (loc - Vector((x,y,z))).length:5.2f} z={loc.z:4.1f} {ob.name[:22]:22s} {matname(ob, fi)[:48]}")
        else:
            print(f"  {adeg:3d}deg MISS")

# Aggregate down-probe: first-hit surfaces in a z band, grouped by material,
# with x/y extents — locates beds/furniture tops without spamming.
def band_scan(label, zcast, zlo, zhi, step=0.2):
    agg = {}
    xi = -11.0
    while xi <= 11.0:
        yi = -9.5
        while yi <= 9.5:
            ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, Vector((xi, yi, zcast)), Vector((0, 0, -1)), distance=zcast - zlo + 0.05)
            if ok and zlo < loc.z < zhi:
                mn = matname(ob, fi)
                a = agg.setdefault(mn, [1e9, -1e9, 1e9, -1e9, 0, 0])
                a[0] = min(a[0], xi); a[1] = max(a[1], xi)
                a[2] = min(a[2], yi); a[3] = max(a[3], yi)
                a[4] += 1; a[5] = loc.z
            yi += step
        xi += step
    print(f"=== BAND {label} z {zlo}..{zhi} ===")
    for mn, a in sorted(agg.items(), key=lambda kv: -kv[1][4]):
        if a[4] >= 4:
            print(f"  {a[4]:5d} pts x[{a[0]:5.1f},{a[1]:5.1f}] y[{a[2]:5.1f},{a[3]:5.1f}] zlast={a[5]:4.2f} {mn[:52]}")

band_scan("upper-furniture", 6.15, 3.55, 4.75)
band_scan("ground-furniture", 2.5, 0.25, 1.2)

# Floor plans: ortho camera straight down, clip_start slices off the roof/ceiling
sc.render.engine = 'BLENDER_EEVEE'
sc.render.resolution_x, sc.render.resolution_y = 1200, 1040
sc.render.image_settings.file_format = 'JPEG'
sc.render.image_settings.quality = 85
w = bpy.data.worlds.new("W"); sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.7, 0.7, 0.72, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
cam = bpy.data.cameras.new("C")
cam.type = 'ORTHO'
cam.ortho_scale = 24.5
co = bpy.data.objects.new("Cam", cam)
sc.collection.objects.link(co)
sc.camera = co
co.location = (0, 0, 12.0)
co.rotation_euler = Euler((0, 0, 0), 'XYZ')  # looks straight down -Z

for name, cut in (("plan-ground", 3.15), ("plan-upper", 6.2)):
    cam.clip_start = 12.0 - cut
    cam.clip_end = 12.0 - cut + 30
    sc.render.filepath = os.path.join(outdir, name + ".jpg")
    bpy.ops.render.render(write_still=True)
    print("PLAN", name)
print("DONE")
