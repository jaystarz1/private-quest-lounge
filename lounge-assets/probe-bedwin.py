import bpy, sys
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=sys.argv[-1])
sc = bpy.context.scene
dg = bpy.context.evaluated_depsgraph_get()
def mn(ob, fi):
    try:
        return ob.data.materials[ob.data.polygons[fi].material_index].name
    except Exception:
        return "?"
def chainray(label, ox, oy, oz, dx, dy, maxd=3.5):
    o0 = Vector((ox, oy, oz)); d = Vector((dx, dy, 0)).normalized(); o = o0
    print(f"== {label} ==")
    for _ in range(8):
        left = maxd - (o - o0).length
        if left <= 0: break
        ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, o + d * 0.012, d, distance=left)
        if not ok:
            print("   clear")
            break
        print(f"   ({loc.x:6.2f},{loc.y:6.2f},{loc.z:4.1f}) {ob.name[:16]} {mn(ob,fi)[:42]}")
        o = loc
chainray("NW north wall z5", -8.5, 8.6, 5.0, 0, 1)
chainray("NW north wall z4.5 x-9.5", -9.5, 8.6, 4.5, 0, 1)
chainray("NW west headboard z5 y7", -9.8, 7.0, 5.0, -1, 0)
chainray("NW west z5.8 y7", -9.8, 7.0, 5.8, -1, 0)
chainray("NE east wall z5", 10.2, 7.0, 5.0, 1, 0)
chainray("NE north wall z5", 9.0, 8.6, 5.0, 0, 1)
chainray("SW west wall z5", -9.9, -3.8, 5.0, -1, 0)
chainray("SW south wall z5", -8.8, -8.8, 5.0, 0, -1)
chainray("gym south z5", -1.5, -8.6, 5.0, 0, -1)
chainray("bath east z5", 9.5, -1.5, 5.0, 1, 0)
print("BWDONE")
