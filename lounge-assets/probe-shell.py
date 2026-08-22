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
def ray_through(label, ox, oy, oz, dx, dy, maxd=16.0):
    print(f"== {label} from ({ox},{oy},{oz}) dir ({dx},{dy}) ==")
    o = Vector((ox, oy, oz)); d = Vector((dx, dy, 0)).normalized()
    trav = 0.0
    for _ in range(12):
        ok, loc, nrm, fi, ob, mw = sc.ray_cast(dg, o + d * 0.02, d, distance=maxd - trav)
        if not ok:
            print("   -> clear to", maxd)
            break
        step = (loc - o).length
        trav += step
        print(f"   hit at ({loc.x:6.2f},{loc.y:6.2f}) d+{step:5.2f} {ob.name[:18]} {mn(ob,fi)[:40]}")
        o = loc
        if trav >= maxd:
            break
# East wall, ground + upper
ray_through("east-ground-y2", 11.0, 2.0, 1.5, 1, 0)
ray_through("east-ground-y6", 11.0, 6.0, 1.5, 1, 0)
ray_through("east-upper-y7", 10.5, 7.0, 5.0, 1, 0)
# West wall
ray_through("west-ground-y2", -10.8, 2.0, 1.5, -1, 0)
ray_through("west-ground-y7", -10.8, 7.0, 1.6, -1, 0)
ray_through("west-upper-y7", -10.4, 7.0, 5.0, -1, 0)
# South
ray_through("south-ground", -4.0, -9.0, 1.5, 0, -1)
ray_through("south-upper", 4.5, -8.8, 5.0, 0, -1)
print("SHELLDONE")
